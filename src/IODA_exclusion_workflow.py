
# coding: utf-8
# Author: Louis Felix Nothias, louisfelix.nothias@gmail.com, June 2020
import pandas as pd
import numpy as np
import sys
import os
import matplotlib.pyplot as plt
from io import StringIO
import warnings
from format_to_qexactive_list import *
from zipfile import ZipFile
from logzero import logger, logfile
import datetime
import gc
import csv
import pyopenms as oms


def make_exclusion_list(input_filename: str, sample: str, intensity:float):
    """From a table with mz, charge, rt, intensities, make an exclusion list from a single sample, above the intensity specified."""
    df_master = pd.read_csv(input_filename, sep=',')
    output_filename = input_filename
    df_master_exclusion_list = df_master[(df_master[sample] != 0)]
    df_master_exclusion_list = df_master[(df_master[sample] > intensity)]
    df_master_exclusion_list.to_csv(output_filename[:-4]+'_EXCLUSION_BLANK.csv', sep=',', index = False)
    #df_master_exclusion_list.sort_values(by=['Mass [m/z]'])
    number_of_ions = 'Initial number of ions = '+ str(df_master.shape[0])
    logger.info(number_of_ions)
    number_of_ions_after_filtering = 'Number of ions after intensity filtering = '+str(df_master_exclusion_list.shape[0]) +', with intensity >'+ str(intensity)
    logger.info(number_of_ions_after_filtering)
    del df_master
    del df_master_exclusion_list
    
def plot_targets_exclusion(input_filename: str, blank_samplename: str, column: str, title: str):
    """From a table, make a scatter plot of a sample"""
    Labels = []
    table0 = pd.read_csv(input_filename, sep=',', header=0)
    fig = plt.figure(figsize=(8,6))
    fig = plt.scatter(column, blank_samplename, data=table0, marker='o', color='lightskyblue',s=3, alpha=0.4)
    Label1 = ['Excluded ions, n = '+ str(table0.shape[0])+ ', median abs. int. = '+ "{0:.2e}".format(table0[blank_samplename].median()) + ', mean abs. int. = '+ "{0:.2e}".format(table0[blank_samplename].mean())]
    Labels.append(Label1)
    plt.yscale('log')
    plt.ylabel('Ion intensity (log scale)', size = 11)
    plt.legend(labels=Labels, fontsize = 8, loc='best', markerscale=5)
    if column == 'Mass [m/z]':
        plt.title(title+', in m/z range', size = 11,  wrap=True)
        plt.xlabel('m/z', size = 10)
        plt.savefig('results/plot_exclusion_scatter_MZ.png', dpi=200)
    if column == 'retention_time':
        plt.title(title+', in retention time range', size =11, wrap=True)
        plt.xlabel('Ret. time (sec)', size = 10)
        plt.savefig('results/plot_exclusion_scatter_RT.png', dpi=200)
    plt.close()
    del table0

def plot_targets_exclusion_range(input_filename: str, blank_samplename: str, title: str):
    Labels = []
    table0 = pd.read_csv(input_filename, sep=',', header=0)
    rt_start = table0['retention_time']-table0['rt_start']
    rt_end = table0['rt_end']-table0['retention_time']
    rt_range = [rt_start, rt_end]
    # Normalizing
    table0[blank_samplename]=((table0[blank_samplename]-table0[blank_samplename].min())/(table0[blank_samplename].max()-table0[blank_samplename].min()))*300
    gradient = table0[blank_samplename].to_list()
    plt.figure(figsize=(9,6))
    plt.errorbar('retention_time','Mass [m/z]', data=table0, xerr=rt_range, fmt='.', elinewidth=0.7, color='lightskyblue', ecolor='grey', capsize=0, alpha=0.3)
    plt.scatter('retention_time','Mass [m/z]', data=table0, s = gradient, c='lightskyblue', marker = "o", facecolors='', edgecolors='red', alpha=0.85, linewidth=0.45)

    Label1 = ['Red circle = intensity, Blue dot = ion apex, Horizontal line = RT range, Ions excluded (n='+ str(table0.shape[0])+')']
    Labels.append(Label1)
    plt.title(title, size =11, wrap=True)
    plt.xlabel('Ret. time (sec)')
    plt.ylabel('m/z')
    plt.legend(labels=Labels, fontsize = 8, loc='upper left', markerscale=0.45)
    plt.savefig('results/plot_exclusion_RT_range_plot.png', dpi=200)
    plt.close()
    del table0

def get_all_file_paths(directory,output_zip_path):
    # initializing empty file paths list
    file_paths = []

    # crawling through directory and subdirectories
    for root, directories, files in os.walk(directory):
        for filename in files:
            # join the two strings in order to form the full filepath.
            filepath = os.path.join(root, filename)
            file_paths.append(filepath)

            # writing files to a zipfile
    with ZipFile(output_zip_path,'w') as zip:
        # writing each file one by one
        for file in file_paths:
            zip.write(file)

    logger.info('All files zipped successfully!')

# Make exclusion list from two dfs

def make_exclusion_from_dfs(input_mzML:int, min_intensity:int, rtexclusionmargininsecs:float, polarity:str):
    input_dir='OpenMS_workflow/OpenMS_output'
    output_dir = 'results'
    
    
    os.system('rm -r results')
    os.system('rm download_results/IODA_exclusion_results.zip')
    os.system('mkdir results')
    os.system('mkdir results/intermediate_files')
    os.system('mkdir download_results')
    now = datetime.datetime.now()
    logger.info(now)
    os.system('rm results/logfile.txt')
    logfile('results/logfile.txt')

    
    # Convert the mzTabs into Tables to generate exclusion list
    logger.info('======')
    logger.info('Starting the IODA-exclusion workflow')
    logger.info('The source of the mzML file is: '+os.path.join("OpenMS_workflow/OpenMS_input/", os.path.basename(input_mzML)))
    logger.info('Input dataframe for narrow feature: '+os.path.join("OpenMS_workflow/OpenMS_output/", os.path.splitext(os.path.basename(input_mzML))[0]) + "_narrow.csv")
    logger.info('Input dataframe for large feature: '+os.path.join("OpenMS_workflow/OpenMS_output/", os.path.splitext(os.path.basename(input_mzML))[0]) + "_large.csv")
    logger.info('======')
    logger.info('======')

    # Read the table to get the filenames
    feature_table = pd.read_csv(os.path.join("OpenMS_workflow/OpenMS_output/", os.path.splitext(os.path.basename(input_mzML))[0]) + "_large.csv", sep=',')
    blank_samplename = feature_table.columns[3]
    del feature_table
    
    name, ext = os.path.splitext(blank_samplename)
    output_filename = output_dir+'/'+name+'.csv'
    logger.info('Blank sample name: was internally renamed as '+ blank_samplename)

    # User-defined parameters
    logger.info('User-defined parameters')
    logger.info('   Minimum ion intensity treshold (count) = '+ str(min_intensity))
    logger.info('   Additional margin for retention time range exclusion (seconds) = '+ str(rtexclusionmargininsecs))

    # Concatenating the tables from narrow and large features:
    
    df_narrow = pd.read_csv(os.path.join("OpenMS_workflow/OpenMS_output/", os.path.splitext(os.path.basename(input_mzML))[0]) + "_narrow.csv", sep=',')
    df_large = pd.read_csv(os.path.join("OpenMS_workflow/OpenMS_output/", os.path.splitext(os.path.basename(input_mzML))[0]) + "_large.csv", sep=',')
    df_concat = pd.concat([df_narrow,df_large])

    del df_narrow
    del df_large
    
    #We expand the margin of the retention time exclusion
    df_concat['rt_start'] = df_concat['rt_start'] - rtexclusionmargininsecs
    df_concat['rt_end'] = df_concat['rt_end'] + rtexclusionmargininsecs

    #Concatening the tables
    df_concat.to_csv(output_filename, sep=',', index=False)

    del df_concat
    
    # Running the table processing
    logger.info('Running the table processing')
    make_exclusion_list(output_filename, blank_samplename, min_intensity)
    logger.info('======')

    # Convert to XCalibur format
    logger.info('Preparing list of excluded ions in XCalibur format (Exactive serie)')
    generate_Exactive_exclusion_table(output_filename[:-4]+'_EXCLUSION_BLANK.csv', blank_samplename, output_filename[:-4]+'_EXCLUSION_BLANK_Exactive.csv', rt_margin=0, polarity=polarity)
    logger.info('Preparing list of excluded ions in XCalibur format (Exploris serie)')
    generate_Exploris_exclusion_table(output_filename[:-4]+'_EXCLUSION_BLANK.csv', blank_samplename, output_filename[:-4]+'_EXCLUSION_BLANK_Exploris.csv', rt_margin=0, polarity=polarity)
    logger.info('======')  
    logger.info('Preparing list of excluded ions in MaxQuant.Live format')
    generate_MQL_exclusion_table(output_filename[:-4]+'_EXCLUSION_BLANK.csv', blank_samplename, output_filename[:-4]+'_EXCLUSION_BLANK_MaxQuantLive.txt', polarity=polarity)
    logger.info('======')

    # === Plot the features  ====
    logger.info('Preparing scatter plots of the excluded ions/features')
    plot_targets_exclusion_range(output_filename[:-4]+'_EXCLUSION_BLANK.csv', blank_samplename, 'Distribution of the excluded ions in the blank sample')
    plot_targets_exclusion(output_filename[:-4]+'_EXCLUSION_BLANK.csv', blank_samplename, 'retention_time', 'Distribution of intensities for the excluded ions in '+ blank_samplename)
    plot_targets_exclusion(output_filename[:-4]+'_EXCLUSION_BLANK.csv', blank_samplename, 'Mass [m/z]', 'Distribution of intensities for the excluded ions in '+ blank_samplename)

    logger.info('======')
    logger.info('Zipping workflow results files')

    # Cleaning the files first
    os.system('mkdir results/intermediate_files')
    os.system('mv '+output_filename[:-4]+'_EXCLUSION_BLANK.csv results/intermediate_files/')
    get_all_file_paths('results','download_results/IODA_exclusion_results.zip')

    logger.info('======')
    logger.info('End the IODA-exclusion workflow processing')
    logger.info('======')
    logger.info('Proceed below with the results visualization')
    gc.collect()


# Make exclusion list from one dataframe
def make_exclusion_from_df(input_filepath:str, min_intensity:int, rtexclusionmargininsecs:float,  polarity:str):
    #Example source filenames
    #input_filename = 'https://drive.google.com/file/d/1LYk-PKsBWl4Pv7c1TlhQwaqwkF2T6sux/view?usp=sharing'
    #input_filename = 'tests/Euphorbia/exclusion/ioda_input/Euphorbia_rogers_latex_Blank_MS1_2uL.mzTab'
    os.system('rm -r results')
    os.system('rm download_results/IODA_exclusion_results.zip')
    os.system('mkdir results')
    os.system('mkdir results/intermediate_files')
    os.system('mkdir download_results')
    os.system('rm results/logfile.txt')
    logfile('results/logfile.txt')
    now = datetime.datetime.now()
    logger.info(now)

    logger.info('Starting the IODA exclusion-from-mzTab-or-dataframe workflow')
    output_dir = 'results'
    logger.info('======')
    logger.info('Getting the intput file')
    logger.info('This is the input: '+input_filepath)
    
    # Getting the df
    os.system('cp '+input_filepath +" " + os.path.join("results/intermediate_files/", os.path.basename(input_filepath)))
    output_filename = os.path.basename(input_filepath)
    logger.info(output_filename)
    df = pd.read_csv(input_filepath, sep=',')

    # Read the table to get the filenames
    blank_samplename = df.columns[3]

    # User-defined parameters
    logger.info('User-defined parameters')
    logger.info('   Minimum ion intensity treshold (count) = '+ str(min_intensity))
    logger.info('   Additional margin for retention time range exclusion (seconds) = '+ str(rtexclusionmargininsecs))

    #We arbitrarly expand the exclusion range from +/- X seconds
    df['rt_start'] = df['rt_start'] - rtexclusionmargininsecs
    df['rt_end'] = df['rt_end'] + rtexclusionmargininsecs

    #Export
    logger.info('Export')
    logger.info(output_filename)
    df.to_csv(output_filename, sep=',', index=False)
              
    del df

    # Running the table processing
    logger.info('Processing the table')
    make_exclusion_list(output_filename, blank_samplename, min_intensity)
    logger.info('======')

    # Convert to XCalibur format
    logger.info('Preparing list of excluded ions in XCalibur format (Exactive serie)')
    generate_Exactive_exclusion_table(output_filename[:-4] + '_EXCLUSION_BLANK.csv', blank_samplename, 'results/'+output_filename[:-4]+'_EXCLUSION_BLANK_Exactive.csv', rt_margin=0, polarity=polarity)
    logger.info('Preparing list of excluded ions in XCalibur format (Exploris serie)')
    generate_Exploris_exclusion_table(output_filename[:-4] + '_EXCLUSION_BLANK.csv', blank_samplename, 'results/'+output_filename[:-4]+'_EXCLUSION_BLANK_Exploris.csv', rt_margin=0, polarity=polarity)
    logger.info('======')
    logger.info('Preparing list of excluded ions in MaxQuant.Live format')
    generate_MQL_exclusion_table(output_filename[:-4] +'_EXCLUSION_BLANK.csv', blank_samplename, 'results/'+output_filename[:-4]+'_EXCLUSION_BLANK_MaxQuantLive.txt', polarity=polarity)
    logger.info('======')


    # === Plot the features  ====
    logger.info('Preparing scatter plots of the excluded ions/features')
    plot_targets_exclusion_range(output_filename[:-4] + '_EXCLUSION_BLANK.csv', blank_samplename, 'Distribution of the excluded ions in the blank sample')
    plot_targets_exclusion(output_filename[:-4] + '_EXCLUSION_BLANK.csv', blank_samplename, 'retention_time', 'Distribution of intensities for the excluded ions in '+ blank_samplename)
    plot_targets_exclusion(output_filename[:-4] + '_EXCLUSION_BLANK.csv', blank_samplename, 'Mass [m/z]', 'Distribution of intensities for the excluded ions in '+ blank_samplename)

    logger.info('=======================')
    logger.info('Zipping workflow results files')

    # Cleaning files first
    #os.system('mkdir results/intermediate_files')
    #os.system('mv results/'+input_filepath+'_EXCLUSION_BLANK.csv intermediate_files/')
    os.system('mv *_EXCLUSION_BLANK.csv results/intermediate_files/')
    os.system('mv results/*_EXCLUSION_BLANK.csv results/intermediate_files/')

    get_all_file_paths('results','download_results/IODA_exclusion_results.zip')
    logger.info('=======================')
    logger.info('End the IODA-exclusion workflow')
    logger.info('=======================')
    logger.info('Proceed below with the results visualization')

if __name__ == "__main__":
    make_exclusion_from_mzTab(str(sys.argv[1]), int(sys.argv[2]), float(sys.argv[3]))
