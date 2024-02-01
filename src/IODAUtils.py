import os
import subprocess
from logzero import logger
import datetime
from datetime import date

def run_subprocess(bashcommand):
    """Run subprocess command with logging."""
    try:
        subprocess.run(bashcommand, shell=True, check=True)
        logger.info('The mzML file was downloaded !')
    except subprocess.CalledProcessError as e:
        # Log detailed error message and exit or handle the error
        logger.error(f"Command '{e.cmd}' returned non-zero exit status {e.returncode}.")
        # Handle the error (e.g., by cleaning up, retrying, or exiting the function)
        raise

def download_copy_mzML(input_file):

    # Test samples
    #source_mzML = "https://raw.githubusercontent.com/lfnothias/IODA_MS/test2/tests/Euphorbia/exclusion/OpenMS_input/Blank.mzML"
    #input_mzML = "tests/Euphorbia/Targeted/OpenMS_input/Euphorbia_rogers_latex_Blank_MS1_2uL.mzML"
    #input_mzML = "https://drive.google.com/file/d/11p2Jau2T-gCQb9KZExWdC7dy8AQWV__l/view?usp=sharing"
    #input_mzML = "ftp://massive.ucsd.edu/MSV000083306/peak/QE_C18_mzML/QEC18_blank_SPE_20181227092326.mzML"

    now = datetime.datetime.now()

    logger.info(now)
    logger.info('STARTING the IODA-targeted WORKFLOW with OpenMS')
    logger.info('======')
    logger.info('Getting the mzML, please wait ...')

    if input_file.startswith(('http','ftp')):

        if 'google' in input_file:

            logger.info('This is the Google Drive download link:'+str(input_file))
            logger.info('Downloading the mzML, please wait ...')

            url_id = input_file.split('/', 10)[5]
            prefixe_google_download = 'https://drive.google.com/uc?export=download&id='
            input_file = prefixe_google_download+url_id
            bashCommand1 = "wget --no-check-certificate '"+input_file+"' -O "+os.path.join(OpenMS_folder+"/OpenMS_input/", os.path.basename(input_file)[:-4] + ".mzML")+" || rm -f "+os.path.join(OpenMS_folder+"/OpenMS_input/", os.path.basename(input_file))
            
            run_subprocess(bashCommand1)

        if 'massive.ucsd.edu' in input_file:

            logger.info('This is the MassIVE repository link: '+str(input_file))
            logger.info('Downloading the mzML, please wait ... ')

            bashCommand4 = "wget -r "+input_file+" -O "+os.path.join(OpenMS_folder+"/OpenMS_input/", os.path.basename(input_file)[:-4] + ".mzML")+" || rm -f "+os.path.join(OpenMS_folder+"/OpenMS_input/", os.path.basename(input_file))

            run_subprocess(bashCommand4)

    elif input_file.endswith(('.raw','.RAW')):
        logger.info('Thermo RAW file detected')
        logger.info('This is the input file path: '+str(input_file))
        bashCommand5 = "mono ThermoRawFileParser/ThermoRawFileParser.exe -i="+input_file+" --logging=2 --ignoreInstrumentErrors --output_file "+os.path.join(OpenMS_folder+"/OpenMS_input/", os.path.basename(input_file)[:-3] + ".mzML")
        logger.info('The file is converting to mzML thanks ThermoRawFileParser v1.3.4, please wait few seconds ...: '+str(input_file))
        logger.info(str(bashCommand5))

        run_subprocess(bashCommand5)

    else:
        #Check the file path is correct for local upload
        logger.info('This is the input file path: '+str(input_file))

        bashCommand3 = "cp "+input_file+" "+os.path.join("OpenMS_workflow/OpenMS_input/", os.path.basename(input_file))

        run_subprocess(bashCommand3)

    if input_file.endswith(('.raw','.RAW')):
        file_path = os.path.join("OpenMS_workflow/OpenMS_input/", os.path.basename(input_file)[:-4] + ".mzML")
        if os.path.exists(file_path):
            logger.info('The mzML file was found !')
        else:
            logger.error('The mzML file was not found after conversion.')

    elif input_file.endswith(('.mzML','.mzml')):
        file_path = os.path.join("OpenMS_workflow/OpenMS_input/", os.path.basename(input_file)[:-5] + ".mzML")
        if os.path.exists(file_path):
            logger.info('The mzML file was found !')
        else:
            logger.error('The mzML file was not found after downloading or copying.')

    # If you are actually copying the mzML file somewhere here, include the copying code
    # Otherwise, adjust or remove this log statement
    logger.info('Copying the mzML to the OpenMS input folder')