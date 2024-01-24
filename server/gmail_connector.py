# -*- coding: utf-8 -*-

from googleapiclient.discovery import build
import base64
import re
import io
from PIL import Image
import json
import os

from zoneinfo import ZoneInfo
from datetime import datetime, timedelta

from google.oauth2.credentials import Credentials

from collections import deque

# find script directory
dir_path = os.path.dirname(os.path.realpath(__file__))

DATE_NOW = datetime.now(ZoneInfo("America/New_York")).date()

class EmailImage():
        # Class to store the details of an image attachment extracted from a Gmail inbox

        def __init__(self, unique_attachment_id : str, temporary_attachment_id : str, message_id : str, text : str, image : Image  = None, display_date : datetime = None):
            self.unique_attachment_id = unique_attachment_id # fixed ID of the attachment for any API call
            self.temporary_attachment_id = temporary_attachment_id # ID of the attachment for the current API call
            self.message_id = message_id # id of the email
            self.text = text # body of the email
            self.image_as_string = image # image as a string
            self.display_date = display_date # date to show the image on the frame

        # Convert to dict for json serialization
        def to_dict(self):
            return {
                "unique_attachment_id": self.unique_attachment_id,
                "temporary_attachment_id": self.temporary_attachment_id,
                "message_id": self.message_id,
                "text": self.text,
                "display_date": self.display_date.isoformat() if self.display_date else None
            }

        @staticmethod
        # Convert from dict to EmailImage
        def from_dict(data):
            display_date = datetime.fromisoformat(data["display_date"]).date() if data["display_date"] else None
            return EmailImage(data["unique_attachment_id"], data["temporary_attachment_id"], data["message_id"], data["text"], display_date=display_date)


class FIFOQueue():
    # First-in First-out Queue (since emails are pulled in chronological order)
    def __init__(self, *elements):
        self._elements = deque(elements)

    def __len__(self):
        return len(self._elements)
    
    # The __iter__ method makes the class iterable 
    def __iter__(self):
        return iter(self._elements)

    def enqueue(self, element):
        # if queue is empty or date of previous element is in the past
        if self.__len__() == 0 or self._elements[-1].display_date < DATE_NOW:
            # add element with today's date
            element.display_date = DATE_NOW

        # if display date of previous element is either today or in the future
        elif self._elements[-1].display_date >= DATE_NOW:
            # add element with +1 day to the previous element
            element.display_date = self._elements[-1].display_date + timedelta(days=1)

        # append element
        self._elements.append(element)

    def dequeue(self):
        # remove first element from queue
        return self._elements.popleft()

    def save_to_file(self, file_path):
        # save the queue to a json file - to make the queue persistent on Cloud Run we need to write it to an external file
        with open(file_path, 'w') as file:
            json.dump({i+1: element.to_dict() for i, element in enumerate(self._elements)}, file)

    def load_from_file(self, file_path):
        # load the queue from a json file
        with open(file_path, 'r') as file:
            elements = json.load(file)
            # Ignore the keys and only use the values
            self._elements = deque(EmailImage.from_dict(element) for element in elements.values())

# class that connects to Gmail and allows you to parse messages
class GmailConnector():

    def __init__(self, creds : Credentials, length_of_queue : int = 3, satellite_emails : list = []):
        self.user_id = 'me'
        # creds are the credentials used to connect to the gmail API
        self.creds = creds
        # A shared Gmail inbox is created specifically for the project. It will receive images from multiple senders.
        # We need to create a filter to only pull images from the right sender.
        # The satellite frame will display images receive from everyone except themselves.
        # The earth frame will only display images from the satellite frame. 
        # Think of it like Apollo and Houston... The spaceship can see everything sent by anyone, whereas  Houston only wants to hear from the spaceship.
        self.length_of_queue = length_of_queue # length of the dynamic image queue
        self.satellite_emails= satellite_emails # emails used by the satellite frame owner 
        #create lists to attachments for all parties
        self.image_queues = {
            "satellite_frame": FIFOQueue(),
            "earth_frame": FIFOQueue(),
        }

        # load queues from file if they exist
        for target in self.image_queues:
            full_queue_path = os.path.join(dir_path, 'queues', f'{target}_queue.json')
            if os.path.exists(full_queue_path):
                self.image_queues[target].load_from_file(full_queue_path)

        # Build API call
        self.service =  build('gmail', 'v1', credentials=self.creds)

    def get_text(self, parts):
        # get text included in the body of an email
        text = None
        if "parts" in parts:
            text = base64.urlsafe_b64decode((parts["parts"][0]["body"]["data"]).encode("ASCII")).decode("utf-8").replace('\r\n', '')
        elif parts['mimeType']=='text/plain':
            text = base64.urlsafe_b64decode((parts["body"]["data"]).encode("ASCII")).decode("utf-8").replace('\r\n', '')
        if text:
            return self.clean_text(text)
    
    def clean_text(self, string : str):
        # remove unwanted characters from text
        string = re.sub(r'\[.*?\]', ' ', string)
        return string
    
    def append_image_information(self, target, unique_attachment_id, temporary_attachment_id, message_id, body_text):

        # If the image is not already in the queue
        if unique_attachment_id not in [item.unique_attachment_id for item in self.image_queues[target]._elements]:
            print(f"Appending image to {target} queue")
            # store image details
            email_image = EmailImage(unique_attachment_id=unique_attachment_id, temporary_attachment_id=temporary_attachment_id, message_id=message_id, text=body_text)
        
            # if the queue is full, remove the first element
            if len(self.image_queues[target]) == self.length_of_queue:
                self.image_queues[target].dequeue()
            
            self.image_queues[target].enqueue(email_image)
    
        else:
            print(f"Image already in {target} queue")

    def pull_specific_image(self, temporary_attachment_id, message_id):
        #store image in utf-8 format
        img_data = self.service.users().messages().attachments().get(userId=self.user_id, messageId=message_id,id=temporary_attachment_id).execute()
        img_data=img_data['data'].encode('UTF-8')
        file_data=base64.urlsafe_b64decode(img_data) #decode string
        image_to_send=Image.open(io.BytesIO(file_data))  #open as an image
        return image_to_send
    
    def build_email_list(self, filter : str):   
        try:
            emails = self.service.users().messages().list(userId=self.user_id, q = (filter)).execute()
            return emails
        except Exception as e:
            print(f"Error in build_email_list: {e}")
            return None
    
    def pull_images_and_update_queue(self, emails_to_parse : dict, target : str):
        # parse emails in chronological order

        # trim list of emails to length of queue
        trimmed_list_of_emails = emails_to_parse['messages'][:self.length_of_queue]

        for message in reversed(trimmed_list_of_emails):
            message_id=(message['id'])
            message_content=self.service.users().messages().get(userId=self.user_id, id=message_id, format='full').execute()

            #find the sender
            for header_parts in message_content['payload']['headers']:
                if header_parts['name']== "From":
                    sender=(header_parts['value'])
            
            #initialize body text to empty 
            body_text = ""
            for parts in message_content['payload']['parts']:
                # get text embedded in email content
                text = self.get_text(parts)
                # only append text if it is not empty
                if text:
                    body_text = text

                # Get attachment & avoid collecting useless attachments that have no name (logos and other stuff)
                # We could also filter on parts['mimetype'] == 'image...' but the code below works well
                if 'attachmentId' in parts['body'] and parts['filename']!="":
                    # Create a unique identifier for the attachment. Unfortunately, the attachment ID provided by the Gmail API is refreshed every time. 
                    # See https://stackoverflow.com/questions/28104157/how-can-i-find-the-definitive-attachmentid-for-an-attachment-retrieved-via-googl
                    # It seems like it doesn't expire though, which means it can always be used to retrieve an attachment.
                    unique_attachment_id = message_id + "_" + parts.get('partId')  # Use message ID and part ID to create a unique identifier
                    temporary_attachment_id = parts['body']['attachmentId'] # This ID changes at every API call

                    print("Found image. Attempting to append to queue...")

                    self.append_image_information(target, unique_attachment_id, temporary_attachment_id, message_id, body_text)


    def pull_attachments(self, target : str):
        print(f"Pulling attachments for the {target}")
        # target is either "satellite_frame" or "earth_frame"
        if target == "satellite_frame": 
            filter = f"-from:{' OR '.join([email for email in self.satellite_emails])}"
        elif target == "earth_frame":
            filter = f"from:{' OR '.join([email for email in self.satellite_emails])}"

        list_of_emails = self.build_email_list(filter)

        if list_of_emails:
            self.pull_images_and_update_queue(list_of_emails, target)
    
    def display_from_queue(self, target : str):
         # target is either "satellite_frame" or "earth_frame"
        
        # get all dates in relevant queue
        dates_in_queue = [item.display_date for item in self.image_queues[target]._elements]

        # go to first date in queue that is today or later
        for index, item in enumerate(dates_in_queue):
            if item >= DATE_NOW:
                break
        
       # get image to display
        image = self.image_queues[target]._elements[index]
        output_text = image.text
        image_to_send = self.pull_specific_image(image.temporary_attachment_id, image.message_id)

        # save queue to file and create dir if it doesn't exist 
        if not os.path.exists(dir_path + '/queues'):
            os.makedirs(dir_path + '/queues')

        self.image_queues[target].save_to_file(os.path.join(dir_path, 'queues', f'{target}_queue.json'))

        return(image_to_send,output_text) # return image and body of first email relevant to the initiator
    