# -*- Code revised May 2023. Olivier Simard-Hanley. -*-
# this is the main file for the DispatchPi flask app

import os
import flask
from flask import send_file
import requests
import json
from io import BytesIO

#google libraries
import google_auth_oauthlib.flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

#local functions
from eink_image import Image_transform
from gmail_connector import GmailConnector


# find script directory
dir_path = os.path.dirname(os.path.realpath(__file__))

#Path to your API credentials file
CLIENT_SECRETS_FILE = os.path.join(dir_path, "secrets/client_secret.json")
#Path to your API Access token file
TOKEN_FILE =  os.path.join(dir_path, 'secrets/token.json')
#Path to your Flask app key
FLASK_KEY= os.path.join(dir_path, 'secrets/flask_key.json')

##AUTH

# This OAuth 2.0 access scope allows to read emails
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
API_SERVICE_NAME = 'gmail'
#API_VERSION = 'v3'

##FLASK APP
app = flask.Flask(__name__)
   
# Flask app key (so that session parameters work)
with open(FLASK_KEY) as secrets_file:
    key_file = json.load(secrets_file)
    app.secret_key = key_file['SECRET_KEY']


def generate_credentials():
  #if there are stored credentials, retrieve them
  credentials = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
  
  #if credentials are expired, refresh
  if not credentials.valid:
    credentials.refresh(Request())
    print("Credentials refreshed!")
        
    #Save credentials to file if they were refreshed 
    with open(TOKEN_FILE, 'w') as token:
      token.write(credentials.to_json())
      print("Credentials saved to file!")

  return credentials
  
def pull_and_display_image(target, creds):
  
  # initialize connector
  gmail_inbox =  GmailConnector(creds=creds, length_of_queue = 10, satellite_emails = ["EMAIL_USED_BY_SATELLITE_FRAME"] )

  # pull attachments
  gmail_inbox.pull_attachments(target=target)

  # get the image to send
  image_to_send, output_text = gmail_inbox.display_from_queue(target=target)
 
  #transform image into a low res format for the eink screen
  transformed_image = Image_transform(imported_image=image_to_send, fit="crop", message=output_text)
  transformed_image = transformed_image.render()
  output = BytesIO()
  transformed_image.save(output, "PNG")
    
  # display the image (don't cache it)
  # output.seek resets the pointer to the beginning of the file 
  output.seek(0)
  return output
  

# define the index
@app.route('/')
def index():

  return ('<table>' + 
          "<tr><td><a href='/satellite_frame''>See the satellite's frame</a></td>" +
          "<tr><td><a href='/earth_frame'>See the earth's frame</a></td>" +
          '<tr><td><a href="/authorize">Test the auth flow directly. You will be sent back to the index</a></td>' +
          '<tr><td><a href="/revoke">Revoke current credentials</a></td>' +
          '</td></tr></table>')

# define view for the satellite frame
@app.route('/satellite_frame')
def api_route_satellite_frame():
  
  #update refresh token if we have a token file
  if os.path.exists(TOKEN_FILE):
    credentials = generate_credentials()
  
  #if there are no credentials, redirect to the authorization flow 
  else:
     #create a session parameter to send the user to the right view after the auth flow
     flask.session['view']="satellite_frame"
     return flask.redirect('authorize')

  #pull and display image
  output = pull_and_display_image(target = "satellite_frame", creds = credentials)
  return send_file(output, mimetype="image/png")


# define view for the earth frame
@app.route('/earth_frame')
def api_route_earth_frame():

  #update refresh token if we have a token file
  if os.path.exists(TOKEN_FILE):
    credentials = generate_credentials()
  
  #if there are no credentials, redirect to the authorization flow 
  else:
     #create a session parameter to send the user to the right view after the auth flow
     flask.session['view']="earth_frame"
     return flask.redirect('authorize')

  #pull and display image
  output = pull_and_display_image(target = "earth_frame", creds = credentials)
  return send_file(output, mimetype="image/png")


# build the authorization flow
@app.route('/authorize')
def authorize():
    
  #if testing the auth flow directly, send to the index
  if 'view' not in flask.session:
      flask.session['view']="index"

  #if we are just testing the auth flow and the credentials are expired, simply refresh them
  if os.path.exists(TOKEN_FILE):
      credentials = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
      if not credentials.valid:
          credentials.refresh(Request())

          #Save credentials to file if they were refreshed
          with open(TOKEN_FILE, 'w') as token:
              token.write(credentials.to_json())

      return flask.redirect(flask.url_for('index'))
    
  #otherwise fetch the full creds
  else: 
      # Create flow instance to manage the OAuth 2.0 Authorization Grant Flow steps.
      flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
          CLIENT_SECRETS_FILE, scopes=SCOPES)
    
      # The URI created here must exactly match one of the authorized redirect URIs
      # for the OAuth 2.0 client, which you configured in the API Console. If this
      # value doesn't match an authorized URI, you will get a 'redirect_uri_mismatch'
      # error.
      flow.redirect_uri = flask.url_for('oauth2callback', _external=True)
    
      authorization_url, state = flow.authorization_url(
          # Enable offline access so that you can refresh an access token without
          # re-prompting the user for permission. Recommended for web server apps.
          access_type='offline',
          # Enable incremental authorization. Recommended as a best practice.
          include_granted_scopes='false')
    
      # Store the state so the callback can verify the auth server response.
      flask.session['state'] = state

      return flask.redirect(authorization_url)

# define the callback
@app.route('/oauth2callback')
def oauth2callback():
  # Specify the state when creating the flow in the callback so that it can
  # verified in the authorization server response.
  state = flask.session['state']

  flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
      CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
  flow.redirect_uri = flask.url_for('oauth2callback', _external=True)

  # Use the authorization server's response to fetch the OAuth 2.0 tokens.
  authorization_response = flask.request.url
  flow.fetch_token(authorization_response=authorization_response)

  # Store credentials in the session.
  credentials = flow.credentials
 
  #save the credentials to file
  with open(TOKEN_FILE, 'w') as token:
      token.write(credentials.to_json())

  return flask.redirect(flask.url_for('index'))

#revoke the credentials : remove the app from authorized apps
#this will reset the refresh token, you'll have to erase the token file to start over
@app.route('/revoke')
def revoke():

  credentials = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

  revoke = requests.post('https://oauth2.googleapis.com/revoke',
      params={'token': credentials.token},
      headers = {'content-type': 'application/x-www-form-urlencoded'})

  status_code = getattr(revoke, 'status_code')
  if status_code == 200:
    return('Credentials successfully revoked.' + index())
    
  else:
    return('An error occurred.' + index())

if __name__ == '__main__':
  #   When running locally, disable OAuthlib's HTTPs verification.
  #   When running in production *do not* leave this option enabled.
  os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

   #Specify a hostname and port that are set as a valid redirect URI
   #for your API project in the Google API Console.
   #set debug to true when testing locally
  app.run('localhost', 8080, debug=True)

else:
  # When running online, use HTTPS for URLs
  # The lines below should be disabled if you are testing the code locally
  # This is handled by the if name == main block above
  class ReverseProxied(object):
      def __init__(self, app):
          self.app = app

      def __call__(self, environ, start_response):
          scheme = environ.get('HTTP_X_FORWARDED_PROTO')
          if scheme:
              environ['wsgi.url_scheme'] = scheme
          return self.app(environ, start_response)
          
  app.wsgi_app = ReverseProxied(app.wsgi_app)

