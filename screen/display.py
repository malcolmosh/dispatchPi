import os
#import sys
import requests
from waveshare_epd import epd7in5_V2
from PIL import Image
import glob, random
import logging
from pathlib import Path

#import local functions
from image_transform_local import Image_transform

# find script directory
dir_path = os.path.dirname(os.path.realpath(__file__))

# logging file
log_file_path = os.path.join(dir_path, "image_log.log")

# initialize logger - you can change it to debut to print the "debug" logging statements if encountering any errors
logging.basicConfig(filename=log_file_path, level=logging.INFO)

#function to display image
def show_image(image):
    try:
        # Display init, clear
        display = epd7in5_V2.EPD()
        display.init() #update 
        
        #display the image
        display.display(display.getbuffer(image)) 

    except IOError as e:
            print(e)

    finally:
        display.sleep()

try:
    logging.info("Pulling image from web")
    # don't forget to point to the proper url view
    filename="https://YOUR_CLOUD_RUN_WEBSITE.a.run.app/PICK_THE_RIGHT_VEW"

    #pull image from web
    response = requests.get(filename, stream=True)
    response.raw.decode_content = True
    image = Image.open(response.raw)

    #push it to the screen
    show_image(image)
    

#if an error occurs (connection slow or URL not accessible), print a random local picture instead
except Exception as web_err:
    logging.error(f"Error pulling image from web: {web_err}")
    logging.info("Pulling image from local directory instead")

    try : 
        pic_path = os.path.join(dir_path, "pics")
        logging.debug(f"Path to local pictures : {pic_path}")
        
        file_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.JPG', '.JPEG', '.PNG', '.BMP', '.GIF'] # create a sect of file extensions
        
        all_images = [p.resolve() for p in Path(pic_path).glob("**/*") if p.suffix in file_extensions]  # Find all matching files for the given patterns in all subfolders of pic_path

        if not all_images:
            raise ValueError("No images found in the local directory. Check that your folder contains all your file types specified.")

        #choose a random image path
        random_image = random.choice(all_images)
        logging.debug(f"Random image path : {random_image}")

        #run the local function to process and display it
        local_image=Image_transform(imported_image=random_image)
        image=local_image.render(fit="crop")
        show_image(image)

    except Exception as err:
        logging.error(f"The local image was not displayed : {err}")