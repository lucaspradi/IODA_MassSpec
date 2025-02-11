
# coding: utf-8
# Author: Louis Felix Nothias, louisfelix.nothias@gmail.com, June 2020
import pandas as pd
import numpy as np
import sys
import os
import matplotlib.pyplot as plt
from io import StringIO
import warnings
from pandas.core.common import SettingWithCopyWarning
from format_to_qexactive_list import *
from zipfile import ZipFile
from logzero import logger, logfile
import datetime
from IODA_split_features import *
from format_to_qexactive_list import *

def convert_mzTab_to_table(input_filename: str,output_filename: str):
    """Take an mzTab containing two samples, output a table with mz, charge, rt, intensities."""
    df = pd.read_csv(input_filename, sep='\t', error_bad_lines=False, warn_bad_lines=False)

    # Get the metadata
    metadata = []
    start_row_consensus = 1
    for row in df['1.0.0']:
        metadata.append(row)
        start_row_consensus += 1

    # Change the type of the list
    metadata = [str(item) for item in metadata]
    [type(item) for item in metadata]

    # Get the filenames
    Filenames = []
    for x in metadata:
        if x.startswith('file:/'):
            x = x.split('/')[-1]
            #Remove duplicates
            if x not in Filenames:
                Filenames.append(x[:-5])

    #print('Filenames in the mzTab')
    #print(Filenames)

    Filename1 = Filenames[0]
    Filename2 = Filenames[1]

    # Display error message for additional samples
    for x in Filenames:
        if x == "ms_run[2]-location":
            Filename3 = Filenames[2]
            logger.info('Warning: There is more than two samples in that mzTab file. We support only two samples currently')
        if x == "ms_run[4]-location":
            Filename4 = Filenames[3]
            logger.info('Warning: There is more than three samples in that mzTab file. We support only two samples currently.')

    # Read and edit the table
    main_df = pd.read_csv(input_filename,sep='\t',index_col=0, skiprows=range(0,start_row_consensus))

    # Get the columns of interest
    feat_int = main_df.loc[:, main_df.columns.str.startswith('peptide_abundance_study_variable')]
    feat_mz = main_df.loc[:, main_df.columns.str.startswith('mass_to_charge')]
    feat_charge = main_df.loc[:, main_df.columns.str.startswith('charge')]
    feat_ret = main_df[['retention_time']]

    # Concat into a master table
    df_master = pd.concat([feat_mz,feat_ret,feat_charge,feat_int], axis=1)

    #Detection of blank
    #print('#Deducing the blank sample by comparing the sum of feature intensity between samples')
    column1_sum = df_master['peptide_abundance_study_variable[1]'].sum()
    logger.info('- For sample '+Filename1+' the sum of feature intensities is = '+str("{:.2e}".format(column1_sum)))
    column2_sum = df_master['peptide_abundance_study_variable[2]'].sum()
    logger.info('- For sample '+Filename2+' the sum of feature intensities = '+str("{:.2e}".format(column2_sum)))
    
    if column1_sum > column2_sum:
    #    logger.info('- The blank sample is assumed to be '+str(Filename2)+' in the mzTab-M')
    #    logger.info('- The samples is assumed to be '+str(Filename1)+' in the mzTab-M')
        df_master.rename(columns={'peptide_abundance_study_variable[1]':Filename2}, inplace=True)
        df_master.rename(columns={'peptide_abundance_study_variable[2]':Filename1}, inplace=True)
    if column1_sum < column2_sum:
    #    logger.info('- The blank sample is assumed to be '+str(Filename1)+' in the mzTab-M')
    #    logger.info('- The samples is assumed to be '+str(Filename2)+' in the mzTab-M')
        df_master.rename(columns={'peptide_abundance_study_variable[1]':Filename1}, inplace=True)
        df_master.rename(columns={'peptide_abundance_study_variable[2]':Filename2}, inplace=True)

    #Replace the sample headers for mandatory samples
    df_master.rename(columns={'mass_to_charge':"Mass [m/z]"}, inplace=True)

    # Replace the sample header for additional samples
    if 'peptide_abundance_study_variable[3]' in df_master.columns:
        df_master.rename(columns={'peptide_abundance_study_variable[3]':Filename3}, inplace=True)
    if 'peptide_abundance_study_variable[4]' in df_master.columns:
        df_master.rename(columns={'peptide_abundance_study_variable[4]':Filename4}, inplace=True)
    df_master = df_master.fillna(0).sort_values('retention_time')
    df_master.to_csv(output_filename, sep=',', index=False)
    return output_filename

def make_exclusion_list_blank(input_filename: str, sample: str):
    """From a table with mz, charge, rt, intensities, keep only features found in the sample specified"""
    df_master = pd.read_csv(input_filename, sep=',')
    df_master_exclusion_list = df_master[(df_master[sample] != 0)]
    df_master_exclusion_list.to_csv(input_filename[:-4]+'_EXCLUSION_BLANK.csv', sep=',', index = False)
    #df_master_exclusion_list.sort_values(by=['Mass [m/z]'])
    logger.info('EXCLUSION')
    logger.info('   Number of ions in the blank sample = ' + str(df_master_exclusion_list.shape[0]) +', with int. != 0 ')

def make_exclusion_list_shared(input_filename: str, blank: str, sample: str):
    """From a table with mz, charge, rt, intensities, keep only features shared amongst the two samples specified"""
    df_master = pd.read_csv(input_filename, sep=',')
    df_master_exclusion_list = df_master[(df_master[blank] != 0) & (df_master[sample] != 0)]
    df_master_exclusion_list.to_csv(input_filename[:-4]+'_EXCLUSION_SHARED.csv', sep=',', index = False)
    #df_master_exclusion_list.sort_values(by=['Mass [m/z]'])
    logger.info("   Number of ions shared between blank and reference samples = " + str(df_master_exclusion_list.shape[0]) +', with int. != 0 ')

def make_targeted_list(input_filename: str, blank: str, sample: str, ratio:float, min_intensity_value:float):
    """From a table with mz, charge, rt, intensities, keep only features that have an intensity above the specified ratio between the sample/blank"""
    df_master = pd.read_csv(input_filename, sep=',')
    df_master_targeted = df_master[(df_master[sample] != 0)]
    df_master_targeted_int = df_master[(df_master[sample] > min_intensity_value)]
    df_master_targeted_ratio = df_master[(df_master[sample]/df_master[blank] > ratio)]
    df_master_targeted_filtered = df_master[(df_master[sample] > min_intensity_value) & (df_master[sample]/df_master[blank] > ratio)]
    df_master_targeted_filtered.to_csv(input_filename[:-4]+'_TARGETED.csv', sep=',', index = False,)
    logger.info('TARGETED METHOD')
    logger.info('   Number of ions in the reference sample = ' + str(df_master_targeted.shape[0]))
    logger.info('   Number of target ions with minimum intensity ('+ str(min_intensity_value)+') = '+ str(df_master_targeted_int.shape[0]))
    logger.info('   Number of target ions with reference sample/blank ratio > '+str(ratio)+', n = '+str(df_master_targeted_ratio.shape[0]))
    logger.info('   Number of target ions with both minimum intensity and ratio filters = '+ str(df_master_targeted_filtered.shape[0]))

def plot_targets_exclusion(input_filename: str, blank_samplename: str, column: str, title: str):
    """From a table, make a scatter plot of a sample"""
    Labels = []
    table0 = pd.read_csv(input_filename, sep=',', header=0)
    fig = plt.figure(figsize=(8,6))
    fig = plt.scatter(column, blank_samplename, data=table0, marker='o', color='blue',s=4, alpha=0.4)
    Label1 = ['n = '+ str(table0.shape[0])+ ', median abs. int. = '+ "{0:.2e}".format(table0[blank_samplename].median()) + ', mean abs. int. = '+ "{0:.2e}".format(table0[blank_samplename].mean())]
    Labels.append(Label1)
    plt.yscale('log')
    plt.ylabel('Ion intensity (log scale)', size = 11)
    plt.legend(labels=Labels, fontsize =10)
    if column == 'Mass [m/z]':
        plt.title(title+', in m/z range', size = 12, wrap=True)
        plt.xlabel('m/z', size = 12)
        plt.savefig(input_filename[:-4]+'_excluded_MZ_scatter_plot.png', dpi=200)
    if column == 'retention_time':
        plt.title(title+', in retention time range range', size =12, wrap=True)
        plt.xlabel('Ret. time (sec)', size = 11)
        plt.savefig(input_filename[:-4]+'_excluded_RT_scatter_plot.png', dpi=200)

    plt.close()

def plot_targets_per_groups(output_filename:str, table_list: str, column:str, output_string:str, sample: str, experiments: int):
    """From a table, make a scatter plot of experiments"""
    #Plot
    Labels = []
    color_list = ['blue','violet','gold','red','green','orange','brown','slateblue','plum','gold','khaki','darkred','limegreen']
    color_list = color_list + color_list + color_list
    for x in range(len(table_list)):
        table = pd.read_csv(table_list[x], sep=',', header=0)
        plt.scatter(column, sample, data=table, s=3, marker='o', c='lightskyblue', edgecolors=color_list[x], alpha=0.45,linewidth=0.7)
        Label = ['Exp. '+str(x+1)+', n = '+ str(table.shape[0])+ ', median = '+ "{0:.2e}".format(table[sample].median()) + ', mean = '+ "{0:.2e}".format(table[sample].mean())]
        Labels.append(Label)

    plt.yscale('log')
    plt.legend(labels=Labels, fontsize =4, loc='best', markerscale=2, fancybox=True, framealpha=0.6)
    plt.title('Target ions distribution per iterative experiment: '+ output_string, wrap=True)
    plt.ylabel('Ion intensity (log scale)',size = 8)

    if column == 'retention_time':
        plt.xlabel('Ret. time (sec)',size = 8)
        plt.savefig(output_filename[:-4]+'_experiment_RT_'+output_string+'_scatter_plot.png', dpi=300)
    if column == 'Mass [m/z]':
        plt.xlabel('Target ion mass [m/z]',size = 8)
        plt.savefig(output_filename[:-4]+'_experiment_MZ_'+output_string+'_scatter_plot.png', dpi=300)
    plt.close()

def plot_targets_per_groups_w_shared(output_filename:str, table_list: str, column:str, output_string: str, input_filename_blank: str, sample: str, blank: str, experiments: int):
    """From a table, make a scatter plot of experiments, and plot the blank too"""
    #Plot
    Labels = []
    color_list = ['blue','violet','gold','red','green','orange','brown','slateblue','plum','gold','khaki','darkred','limegreen']
    color_list = color_list + color_list + color_list
    for x in range(len(table_list)):
        table = pd.read_csv(table_list[x], sep=',', header=0)
        plt.scatter(column, sample, data=table, marker='.', c='orange', edgecolors=color_list[x], s=3, alpha=0.45,linewidth=0.6)
        Label = ['Exp. '+str(x+1)+', n = '+ str(table.shape[0])+ ', median = '+ "{0:.2e}".format(table[sample].median()) + ', mean = '+ "{0:.2e}".format(table[sample].mean())]
        Labels.append(Label)

    # Show shared features between blank and sample
    table_blank = pd.read_csv(input_filename_blank, sep=',', header=0)
    plt.scatter(column, blank, data=table_blank, marker='v', color='black', s=1, alpha=0.8)
    Label2 = ['Blank (excluded ion), n = '+ str(table_blank.shape[0])+ ', median = '+ "{0:.2e}".format(table_blank[blank].median())  + ', mean = '+ "{0:.2e}".format(table_blank[blank].mean())]
    Labels.append(Label2)

    plt.yscale('log')
    plt.title('Target ions distribution per iterative experiment (w. excluded ions)', size =9, wrap=True)
    plt.ylabel('Ion intensity (log scale)',size = 8)
    plt.legend(labels=Labels, fontsize =4, loc='best', markerscale=2, fancybox=True, framealpha=0.7)
    if column == 'retention_time':
        plt.xlabel('Target ion retention time (sec)',size = 8)
        plt.savefig(output_filename[:-4]+'_experiment_blank_shared_RT_'+output_string+'_scatter_plot.png', dpi=300)
        plt.savefig('experiment_blank_shared_RT_'+output_string+'_scatter_view.png', dpi=300)
    if column == 'Mass [m/z]':
        plt.xlabel('Target ion mass [m/z]', size = 8)
        plt.savefig(output_filename[:-4]+'_experiment_blank_shared_MZ_'+output_string+'_scatter_plot.png', dpi=300)
        plt.savefig('experiment_blank_shared_MZ_'+output_string+'_scatter_view.png', dpi=300)
    plt.close()


def plot_targets_per_groups_w_shared_gradient(output_filename:str, table_list: str, output_string: str, input_filename_blank: str, sample: str, blank: str, experiments: int):
    """From a table, make a scatter plot of experiments, and plot the blank too"""
    #Plot
    Labels = []
    color_list = ['blue','violet','gold','red','green','orange','brown','slateblue','plum','gold','khaki','darkred','limegreen']
    color_list = color_list + color_list + color_list
    for x in range(len(table_list)):
        table = pd.read_csv(table_list[x], sep=',', header=0)
        table[table.columns[-1]] = np.log(table[table.columns[-1]])
        table[table.columns[-1]]=(((table[table.columns[-1]]-table[table.columns[-1]].min())/20)/(table[table.columns[-1]].max()-table[table.columns[-1]].min()))*20
        #table[table.columns[-1]] = table[table.columns[-1]] /100000
        gradient = table[table.columns[-1]].to_list()
        plt.scatter('retention_time','Mass [m/z]', data=table, s = gradient, c='orange', marker = "o", facecolors='', edgecolors=color_list[x], alpha=0.8, linewidth=0.5)
        Label = ['Exp. '+str(x+1)+', n = '+ str(table.shape[0])+ ', median = '+ "{0:.2e}".format(table[sample].median()) + ', mean = '+ "{0:.2e}".format(table[sample].mean())]
        Labels.append(Label)

    # Show shared features between blank and sample
    table_blank = pd.read_csv(input_filename_blank, sep=',', header=0)
    plt.scatter('retention_time','Mass [m/z]', data=table_blank, marker='v', c='black', facecolors='', s = 2, alpha=0.8)
    Label2 = ['Blank (excluded ion), n = '+ str(table_blank.shape[0])+ ', median = '+ "{0:.2e}".format(table_blank[blank].median())  + ', mean = '+ "{0:.2e}".format(table_blank[blank].mean())]
    Labels.append(Label2)

    #plt.yscale('log')
    plt.title('Target ions coordinates per iterative experiment (w. excluded ions).', size =9, wrap=True)
    plt.ylabel('Target ion mass [m/z]',size = 8)
    plt.legend(labels=Labels, fontsize =4, loc='best', markerscale=1.5, fancybox=True, framealpha=0.7)
    plt.xlabel('Target ion retention time (sec)',size = 8)
    plt.savefig(output_filename[:-4]+'_experiment_blank_shared_MZ_RT_'+output_string+'_scatter_plot.png', dpi=300)
    plt.savefig('experiment_blank_shared_MZ_RT_'+output_string+'_scatter_view.png', dpi=300)
    plt.close()


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

# Make targeted list from mzTab
def make_targeted_list_from_feature_table_or_mztab(input_filepath:int, experiment_number:int, ratio:float, min_intensity_value:int, pretarget_rt_margin:float, posttarget_rt_margin:float, window_bin:int, min_int_apex_ratio:float):
    os.system('rm -r results_targeted')
    os.system('rm download_results/IODA_targeted_results.zip')
    os.system('mkdir results_targeted')
    os.system('mkdir download_results')
    os.system('rm results/logfile.txt')
    logfile('results_targeted/logfile.txt')

    logger.info('STARTING THE IODA targeted-from-FeatureTable WORKFLOW')
    if input_filepath == 'pyOpenMS_generated':
        logger.info('The feature table was generated with the IODA-OpenMS workflow')
        consensus_df_path = "OpenMS_workflow/OpenMS_output/consensus.csv"
        logger.info('This is the output file path: '+str(consensus_df_path))
        
    elif input_filepath.endswith('mzTab'):
        logger.info('An mzTab was provided')
        consensus_df_path = "OpenMS_workflow/OpenMS_output/consensus.csv"
        convert_mzTab_to_table(input_filepath, consensus_df_path)
        logger.info('This is the output file path of the converted mzTab: '+str(consensus_df_path))
             
    else:
        logger.info('The feature table was provided by the user ')
        os.system('mv '+input_filepath+' OpenMS_workflow/OpenMS_output/consensus.csv')
        consensus_df_path = "OpenMS_workflow/OpenMS_output/consensus.csv"
        logger.info('This is the output file path: '+str(consensus_df_path))
        
    now = datetime.datetime.now()
    logger.info(now)
    
    output_dir = 'results_targeted'
    logger.info('======')
    logger.info('Getting the input file')
    logger.info('======')

    # Read the table to get the filenames
    feature_table = pd.read_csv(consensus_df_path)
    samplename = feature_table.columns[-1]
    logger.info('Assumed reference sample filename: '+samplename)
    blank_samplename = feature_table.columns[-2]
    logger.info('Assumed blank filename: ' +blank_samplename)
    logger.info('======')

    # User-defined parameters
    logger.info('User-defined parameters')
    logger.info('   Ratio between sample/blank intensity for valid target ions = ' + str(ratio))
    logger.info('   Minimum intensity for ion filtering in the reference sample = '+ str(min_intensity_value))
    logger.info('   Number of iterative experiment(s) for target ions = ' + str(experiment_number))
    logger.info('======')

    # Hard coded parameters
    logger.info('Retention time range parameters:')
    rt_window_excluded_ion = pretarget_rt_margin + posttarget_rt_margin
    logger.info('   Excluded ion retention time (sec.) = ' + str(rt_window_excluded_ion))
    logger.info('   Pre-target ion retention time margin (sec.) = ' + str(pretarget_rt_margin))
    logger.info('   Post-target ion retention time margin (sec.) = ' + str(posttarget_rt_margin))
    logger.info('   Minimum intensity apex ratio (only Exploris serie) = ' + str(min_int_apex_ratio))

    #Parameter for split features
    logger.info('======')
    logger.info('Splitting parameters')
    logger.info('   Retention time window (sec.) for binning target ions = ' +str(window_bin))

    logger.info('======')

    # Running the table processing
    logger.info('Processing the ions ...')
    logger.info('======')
    make_exclusion_list_blank(consensus_df_path, blank_samplename)
    make_exclusion_list_shared(consensus_df_path, blank_samplename, samplename)
    logger.info('======')
    make_targeted_list(consensus_df_path, blank_samplename, samplename, ratio, min_intensity_value)
    logger.info('======')

    # Split the tables for multiple experiment_number
    logger.info('Splitting the target ions per intensity in a given retention time bin')
    from IODA_split_features import split_features
    split_features(consensus_df_path[:-4]+'_TARGETED.csv', consensus_df_path[:-4]+'_TARGETED.csv', samplename, window_bin, experiment_number)
    split_table = pd.read_csv(consensus_df_path[:-4]+'_TARGETED_1.csv', sep=',', header=0)
    logger.info('   Number of target ions per experiment n = '+str(split_table.shape[0]))
    logger.info('======')

    # Generate the filename list
    table_list = []
    for x in range(1,experiment_number+1):
        table_list.append(consensus_df_path[:-4]+'_TARGETED_'+str(x)+'.csv')


    # === OUTPUT FILES BELOW + LOG ====
    logger.info('Plotting the ions ... please wait ...')
    plot_targets_exclusion(consensus_df_path[:-4]+'_EXCLUSION_SHARED.csv', blank_samplename, 'retention_time', 'Intensity distribution of ions excluded')
    plot_targets_exclusion(consensus_df_path[:-4]+'_EXCLUSION_SHARED.csv', blank_samplename, 'Mass [m/z]', 'Intensity distribution of ions excluded')
    plot_targets_per_groups(consensus_df_path, table_list, 'retention_time', 'TARGETED', samplename, experiment_number)
    plot_targets_per_groups(consensus_df_path, table_list, 'Mass [m/z]', 'TARGETED', samplename, experiment_number)
    plot_targets_per_groups_w_shared(consensus_df_path, table_list, 'retention_time','TARGETED', consensus_df_path[:-4]+'_EXCLUSION_SHARED.csv', samplename, blank_samplename, experiment_number)
    plot_targets_per_groups_w_shared(consensus_df_path, table_list, 'Mass [m/z]','TARGETED', consensus_df_path[:-4]+'_EXCLUSION_SHARED.csv', samplename, blank_samplename, experiment_number)
    plot_targets_per_groups_w_shared_gradient(consensus_df_path, table_list,'TARGETED', consensus_df_path[:-4]+'_EXCLUSION_SHARED.csv', samplename, blank_samplename, experiment_number)

    logger.info('======')

    # Convert to Exactive serie format
    logger.info('Converting tables to XCalibur format (Exactive serie) ...')
    for x in range(1,experiment_number+1):
            generate_QE_list(consensus_df_path[:-4]+'_EXCLUSION_BLANK.csv', consensus_df_path[:-4]+'_EXCLUSION_BLANK_Exactive_exp_'+str(x)+'.csv', rt_window_excluded_ion/2, rt_window_excluded_ion/2)
            generate_QE_list(consensus_df_path[:-4]+'_EXCLUSION_SHARED.csv', consensus_df_path[:-4]+'_EXCLUSION_SHARED_Exactive_exp_'+str(x)+'.csv', rt_window_excluded_ion/2, rt_window_excluded_ion/2)
            generate_QE_list(consensus_df_path[:-4]+'_TARGETED_'+str(x)+'.csv', consensus_df_path[:-4]+'_TARGETED_Exactive_exp_'+str(x)+'.csv', pretarget_rt_margin, posttarget_rt_margin)
    logger.info('======')
    
    # Convert to Exploris serie format
    logger.info('Converting tables to XCalibur format (Exploris serie) ...')
    for x in range(1,experiment_number+1):
            generate_Exploris_list(consensus_df_path[:-4]+'_EXCLUSION_BLANK.csv', consensus_df_path[:-4]+'_EXCLUSION_BLANK_Exploris_exp_'+str(x)+'.csv', rt_window_excluded_ion/2, rt_window_excluded_ion/2)
            generate_Exploris_list(consensus_df_path[:-4]+'_EXCLUSION_SHARED.csv', consensus_df_path[:-4]+'_EXCLUSION_SHARED_Exploris_exp_'+str(x)+'.csv', rt_window_excluded_ion/2, rt_window_excluded_ion/2)
            generate_Exploris_list(consensus_df_path[:-4]+'_TARGETED_'+str(x)+'.csv', consensus_df_path[:-4]+'_TARGETED_Exploris_exp_'+str(x)+'.csv', pretarget_rt_margin, posttarget_rt_margin)
            generate_Exploris_list_int(consensus_df_path[:-4]+'_TARGETED_'+str(x)+'.csv', consensus_df_path[:-4]+'_TARGETED_Exploris_int_exp_'+str(x)+'.csv', pretarget_rt_margin, posttarget_rt_margin, min_int_apex_ratio)
    logger.info('======')
       

        # Convert the MaxQuant.Live format
    logger.info('Converting tables to MaxQuant.Live format ...')
    for x in range(1,experiment_number+1):
            generate_MQL_list(consensus_df_path[:-4]+'_EXCLUSION_BLANK.csv', consensus_df_path[:-4]+'_EXCLUSION_BLANK_MaxQuantLive_exp_'+str(x)+'.csv', 0, rt_window_excluded_ion)
            generate_MQL_list(consensus_df_path[:-4]+'_EXCLUSION_SHARED.csv', consensus_df_path[:-4]+'_EXCLUSION_SHARED_MaxQuantLive_exp_'+str(x)+'.csv', 0, rt_window_excluded_ion)
            generate_MQL_list(consensus_df_path[:-4]+'_TARGETED_'+str(x)+'.csv', consensus_df_path[:-4]+'_TARGETED_MaxQuantLive_exp_'+str(x)+'.csv', pretarget_rt_margin , posttarget_rt_margin)
            
    logger.info('======')
    logger.info('Cleaning and zipping workflow results files ...')

    # Cleaning files first

    #mkdir Exactive

    dir_path = "OpenMS_workflow/OpenMS_output"
    old_pattern = "consensus_"
    new_pattern = samplename[:-5]+'_blank_'

    # loop through files in the directory
    for filename in os.listdir(dir_path):
        # check if it's a file (not a folder)
        if os.path.isfile(os.path.join(dir_path, filename)):
            # split the file path into directory, base filename, and extension
            base_filename, ext = os.path.splitext(filename)
            # replace the string pattern in the base filename
            new_base_filename = base_filename.replace(old_pattern, new_pattern)
            # create the new file path
            new_filepath = os.path.join(dir_path, new_base_filename + ext)
            old_filepath = os.path.join(dir_path, filename)
            # rename the file
            os.rename(old_filepath, new_filepath)
        
    os.system('mkdir results_targeted/Exactive')
    os.system('mkdir results_targeted/Exactive/exclusion')
    os.system('mkdir results_targeted/Exactive/targeted')
    # mv files Exactive
    os.system('mv OpenMS_workflow/OpenMS_output/*EXCLUSION_BLANK_Exactive* results_targeted/Exactive/exclusion')
    os.system('mv OpenMS_workflow/OpenMS_output/*EXCLUSION_SHARED_Exactive* results_targeted/Exactive/exclusion')
    os.system('mv OpenMS_workflow/OpenMS_output/*TARGETED_Exactive* results_targeted/Exactive/targeted')

    #mkdir Exploris
    os.system('mkdir results_targeted/Exploris')
    os.system('mkdir results_targeted/Exploris/exclusion')
    os.system('mkdir results_targeted/Exploris/targeted')
    # mv files Exploris
    os.system('mv OpenMS_workflow/OpenMS_output/*EXCLUSION_BLANK_Exploris* results_targeted/Exploris/exclusion')
    os.system('mv OpenMS_workflow/OpenMS_output/*EXCLUSION_SHARED_Exploris* results_targeted/Exploris/exclusion')
    os.system('mv OpenMS_workflow/OpenMS_output/*TARGETED_Exploris* results_targeted/Exploris/targeted')
    
    #mkdir MQL
    os.system('mkdir results_targeted/MaxQuantLive')
    os.system('mkdir results_targeted/MaxQuantLive/exclusion')
    os.system('mkdir results_targeted/MaxQuantLive/targeted')
    # mv files MQL
    os.system('mv OpenMS_workflow/OpenMS_output/*EXCLUSION_BLANK_MaxQuantLive* results_targeted/MaxQuantLive/exclusion')
    os.system('mv OpenMS_workflow/OpenMS_output/*EXCLUSION_SHARED_MaxQuantLive* results_targeted/MaxQuantLive/exclusion')
    os.system('mv OpenMS_workflow/OpenMS_output/*TARGETED_MaxQuantLive* results_targeted/MaxQuantLive/targeted')

    # mkdir intermediate files
    os.system('mkdir results_targeted/intermediate_files')
    os.system('mkdir results_targeted/intermediate_files/converted')
    os.system('mkdir results_targeted/intermediate_files/exclusion')
    os.system('mkdir results_targeted/intermediate_files/targeted')
    os.system('mkdir results_targeted/plots')
    
    # mv plots
    os.system('mv OpenMS_workflow/OpenMS_output/*TARGETED_scatter_plot* results_targeted/plots')

    # mv intermediate files
    os.system('mv OpenMS_workflow/OpenMS_output/*EXCLUSION_BLANK* results_targeted/intermediate_files/exclusion')
    os.system('mv OpenMS_workflow/OpenMS_output/*EXCLUSION_SHARED* results_targeted/intermediate_files/exclusion')
    os.system('mv OpenMS_workflow/OpenMS_output/*TARGETED_* results_targeted/intermediate_files/targeted')

    # mv logr
    os.system('mv OpenMS_workflow/OpenMS_output/*TARGETED.csv results_targeted/intermediate_files/converted')
    os.system('mv OpenMS_workflow/OpenMS_output/*blank.csv results_targeted/intermediate_files/converted')
    os.system('mv OpenMS_workflow/logfile_IODA_OpenMS_from_mzML.txt results_targeted/intermediate_files/')

    get_all_file_paths('results_targeted','download_results/IODA_targeted_results.zip')

    logger.info('======')
    logger.info('END OF THE IODA-targeted-from-mzML WORKFLOW')
    logger.info('======')
    print(' ')

if __name__ == "__main__":
    make_targeted_list_from_mzTab(str(sys.argv[1]),int(sys.argv[2]),float(sys.argv[3]),float(sys.argv[4]),float(sys.argv[5]),int(sys.argv[6]),float(sys.argv[7]))
