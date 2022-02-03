# dispatchPi
## A communicating e-paper picture frame, powered by a Raspberry Pi Zero

The frame's job is to display an image from a fixed URL at specific intervals. There is a Flask app hosted at this address. Whenever it is pinged, it pulls the latest image received in a Gmail inbox, with the help of the Gmail API and Auth 2.0.

There are two folders to browse here:

- **Screen** contains the code found on the Raspberry Pi device
- **Server** holds the code hosted online in a dockerized Flask app 

To replicate this project, you will most likely need : 

- A raspberry pi and a e-paper screen
- A Google Developer account
- A Gmail API key
- A Flask app to host on Google Cloud Run
- A love for trial and error! 
- An inclination to tinker with electronics and tiny screws (@$&!****)
