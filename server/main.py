# -*- coding: utf-8 -*-
# version v0.1

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
from image_transform import Image_transform
from image_import import pull_attachment


##SECRETS

#Path to your API credentials file
CLIENT_SECRETS_FILE = "secrets/client_secret.json"
#Path to your API Access token file
TOKEN_FILE = 'secrets/token.json'
#Path to your Flask app key
FLASK_KEY='secrets/flask_key.json'

##AUTH

# This OAuth 2.0 access scope allows to read emails
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
API_SERVICE_NAME = 'gmail'
#API_VERSION = 'v3'

##FLASK APP
app = flask.Flask(__name__)

#use https for URLs
class ReverseProxied(object):
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        scheme = environ.get('HTTP_X_FORWARDED_PROTO')
        if scheme:
            environ['wsgi.url_scheme'] = scheme
        return self.app(environ, start_response)
        
app.wsgi_app = ReverseProxied(app.wsgi_app)

# Flask app key (so that session parameters work)
with open(FLASK_KEY) as secrets_file:
    key_file = json.load(secrets_file)
    app.secret_key = key_file['SECRET_KEY']

@app.route('/')
def index():
  return print_index_table()


@app.route('/north')
def api_route_north():
  
  if os.path.exists(TOKEN_FILE):
      #if there are stored credentials, retrieve them
      credentials = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
      
        #if credentials are expired, refresh
      if not credentials.valid:
           credentials.refresh(Request())
                
           #Save credentials to file if they were refreshed 
           with open(TOKEN_FILE, 'w') as token:
                 token.write(credentials.to_json())

  #if there are no credentials, redirect to the authorization flow 
  else:
     #set the session user to where we want the auth flow to redirect
     flask.session['view']="north"
     return flask.redirect('authorize')
  
  #import image from the gmail API
  #credentials = Credentials.from_authorized_user_file('secrets/token.json', SCOPES)
  image_to_send,output_text = pull_attachment(identifiant="north", creds=credentials)
    
  #transform image into a low res format for the eink screen
  transformed_image = Image_transform(imported_image=image_to_send, fit="crop", message=output_text)
  transformed_image = transformed_image.render()
  output = BytesIO()
  transformed_image.save(output, "PNG")
    
  #display the image (don't cache it)
  output.seek(0)
  return send_file(output, mimetype="image/png", cache_timeout=0)

@app.route('/south')
def api_route_south():

  
  if os.path.exists(TOKEN_FILE):
      #if there are stored credentials, retrieve them
      credentials = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
      
        #if credentials are expired, refresh
      if not credentials.valid:
           credentials.refresh(Request())
           
           #Save credentials to file if they were refreshed 
           with open(TOKEN_FILE, 'w') as token:
                 token.write(credentials.to_json())

  #if there are no credentials, redirect to the authorization flow 
  #set the session user to where we want the auth flow to redirect
  else:
     flask.session['view']="south"
     return flask.redirect('authorize')
  
  #import image from the gmail API
  #credentials = Credentials.from_authorized_user_file('secrets/token.json', SCOPES)
  image_to_send,output_text = pull_attachment(identifiant="south", creds=credentials)
    
  #transform image into a low res format for the eink screen
  transformed_image = Image_transform(imported_image=image_to_send, fit="crop", message=output_text)
  transformed_image = transformed_image.render()
  output = BytesIO()
  transformed_image.save(output, "PNG")
    
  #display the image (don't cache it)
  output.seek(0)
  return send_file(output, mimetype="image/png", cache_timeout=0)


@app.route('/authorize')
def authorize():
    
  #if testing the auth flow directly, choose a view
  if 'view' not in flask.session:
      flask.session['view']="north"
  
  #if we are just testing the auth flow and the credentials are expired, simply refresh them
  if  os.path.exists(TOKEN_FILE):
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

  if flask.session['view']=="north":
      return flask.redirect(flask.url_for('api_route_north'))
  
  elif flask.session['view']=="south":
      return flask.redirect(flask.url_for('api_route_south'))


#revoke the credentials : remove the app from authorized apps
#this will reset the refresh token
@app.route('/revoke')
def revoke():

  credentials = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

  revoke = requests.post('https://oauth2.googleapis.com/revoke',
      params={'token': credentials.token},
      headers = {'content-type': 'application/x-www-form-urlencoded'})

  status_code = getattr(revoke, 'status_code')
  if status_code == 200:
    return('Credentials successfully revoked.' + print_index_table())
  else:
    return('An error occurred.' + print_index_table())


def print_index_table():
  return ('<table>' +
          '<tr><td><a href="/north">View from the north</a></td>' +
          '<td>See the latest picture received in the north.</td></tr>' +
          '<tr><td><a href="/south">View from the south</a></td>' +
          '<td>See the latest picture received in the south.</td></tr>' +
          '<tr><td><a href="/authorize">Test the auth flow directly.</a></td>' +
          '<td>Go directly to the authorization flow. You will be sent back to the index.</td></tr>' +
          '<tr><td><a href="/revoke">Revoke current credentials</a></td>' +
          '<td>Revoke the access token.' +
          '</td></tr></table>')

if __name__ == '__main__':
   #When running locally, disable OAuthlib's HTTPs verification.
   #ACTION ITEM for developers:
    #   When running in production *do not* leave this option enabled.
  #os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

   #Specify a hostname and port that are set as a valid redirect URI
   #for your API project in the Google API Console.
  app.run('localhost', 8080, debug=False)