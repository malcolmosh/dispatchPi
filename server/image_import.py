# -*- coding: utf-8 -*-

from __future__ import print_function

from googleapiclient.discovery import build

import base64
import re


def pull_attachment(identifiant, creds):

    # Call the Gmail API
    service = build('gmail', 'v1', credentials=creds)
    userId='me'
    
    #list emails
    results = service.users().messages().list(userId=userId).execute()
    
    #create list of to store message ids and attachment ids when both exist
    list_attachments_sud=[]
    list_attachments_nord=[]
    
    #get id of first 10 emails
    for idx,message in enumerate(results['messages'][0:11]):
        message_id=(message['id'])
        message_content=service.users().messages().get(userId=userId, id=message_id, format='full').execute()
        #assign default body text to empty
        data=""

        #find the sender
        for header_parts in message_content['payload']['headers']:
            if header_parts['name']== "From":
                expediteur=(header_parts['value'])
        
        identifiant_nord=["INSERT ALL EMAIL ADDRESSES THAT THE PERSON IN THE NORTH WILL USE"]

        for parts in message_content['payload']['parts']:
            #get text embedded in email content
            
            #if part has another part
            if "parts" in parts:
                data=(base64.urlsafe_b64decode((parts["parts"][0]["body"]["data"]).encode("ASCII")).decode("utf-8").replace('\r\n', ''))
                #remove text between brackets
                data=re.sub(r'\[.*?\]', ' ', data)
                
            #else if parts are not recursive
            elif parts['mimeType']=='text/plain':
                data=(base64.urlsafe_b64decode((parts["body"]["data"]).encode("ASCII")).decode("utf-8").replace('\r\n', ''))
                #remove text between brackets
                data=re.sub(r'\[.*?\]', ' ', data)
                
            #get attachment
            #avoid collecting useless attachments that have no name (logos and other stuff)
            if 'attachmentId' in parts['body'] and parts['filename']!="":
                att_id = parts['body']['attachmentId']
               
                #if the sender is the north
                if any(x in expediteur for x in identifiant_nord):
                    list_attachments_sud.append([message_id,att_id, data])
                #if the sender is the south
                else:
                    list_attachments_nord.append([message_id,att_id, data])
        data=""
                
    if identifiant=="north":
    #get first available attachment
        img_data = service.users().messages().attachments().get(userId=userId, messageId=list_attachments_nord[0][0],id=list_attachments_nord[0][1]).execute()
        img_data=img_data['data'].encode('UTF-8')
        output_text=list_attachments_nord[0][2]

        
    elif identifiant=="south":
    #get first available attachment
        img_data = service.users().messages().attachments().get(userId=userId, messageId=list_attachments_sud[0][0],id=list_attachments_sud[0][1]).execute()
        img_data=img_data['data'].encode('UTF-8')
        output_text=list_attachments_sud[0][2]
    
    #decode string
    file_data=base64.urlsafe_b64decode(img_data)
    
    #open as an image
    import io
    from PIL import Image
    image_to_send=Image.open(io.BytesIO(file_data))
    
    return(image_to_send,output_text)

