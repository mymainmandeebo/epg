import xml.etree.ElementTree as ET
import os
import requests
import gzip
import shutil
from datetime import datetime
import yaml
from github import Github

def load_config(yaml_file):
    with open(yaml_file, 'r') as file:
        config = yaml.safe_load(file)
    return config

def download_and_decompress_epg_files(epg_sources, temp_folder):
    if not os.path.exists(temp_folder):
        os.makedirs(temp_folder)
    
    epg_files = []
    
    for source in epg_sources:
        url = source['url']
        gz_file_name = os.path.join(temp_folder, url.split('/')[-1])
        xml_file_name = gz_file_name.replace('.gz', '')

        # Download the .gz file
        response = requests.get(url)
        
        if response.status_code == 200:
            with open(gz_file_name, 'wb') as f:
                f.write(response.content)
            print(f"Downloaded {gz_file_name}")
            
            # Decompress the .gz file to get the XML file
            with gzip.open(gz_file_name, 'rb') as f_in:
                with open(xml_file_name, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            print(f"Decompressed {gz_file_name} to {xml_file_name}")
            
            epg_files.append(xml_file_name)
        else:
            print(f"Failed to download {url}")
    
    return epg_files

def combine_epg_files(input_files, combined_xml_file):
    if not input_files:
        print("No XML files found.")
        return None
    
    root = ET.Element("tv")  # Create a root element for the combined XML

    for file in input_files:
        tree = ET.parse(file)
        file_root = tree.getroot()

        # Append each <programme> element to the root of the combined XML
        for programme in file_root.findall('programme'):
            root.append(programme)

    # Write the combined XML to a file
    tree = ET.ElementTree(root)
    tree.write(combined_xml_file, encoding='utf-8', xml_declaration=True)
    print(f"Combined XML file saved as {combined_xml_file}")
    
    return combined_xml_file

def compress_to_gz(file_name):
    gz_file_name = f"{file_name}.gz"
    with open(file_name, 'rb') as f_in:
        with gzip.open(gz_file_name, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    print(f"Compressed {file_name} to {gz_file_name}")
    return gz_file_name

def upload_to_github(repo_name, file_paths, github_token):
    from github import Github, BadCredentialsException, UnknownObjectException
    import os
    
    try:
        # Authenticate with GitHub
        g = Github(github_token)
        repo = g.get_user().get_repo(repo_name)
        
        for file_path in file_paths:
            file_name = os.path.basename(file_path)
            with open(file_path, 'rb') as file:
                content = file.read()
            
            try:
                # Check if the file already exists in the repo
                repo_file = repo.get_contents(file_name)
                # If it exists, update it
                repo.update_file(repo_file.path, f"Update {file_name}", content, repo_file.sha)
                print(f"Updated {file_name} in {repo_name} repository.")
            except UnknownObjectException:
                # If it doesn't exist, create a new file
                repo.create_file(file_name, f"Add {file_name}", content)
                print(f"Uploaded {file_name} to {repo_name} repository.")
    except BadCredentialsException:
        print("Invalid GitHub token. Please check your token and its permissions.")
    except Exception as e:
        print(f"An error occurred: {e}")

def cleanup_temp_folder(temp_folder):
    if os.path.exists(temp_folder):
        for file_name in os.listdir(temp_folder):
            file_path = os.path.join(temp_folder, file_name)
            if os.path.isfile(file_path):
                os.remove(file_path)
                print(f"Removed temporary file {file_path}")
        os.rmdir(temp_folder)
        print(f"Removed temporary folder {temp_folder}")

def archive_old_combined_file(combined_xml_file, archive_folder):
    if os.path.isfile(combined_xml_file):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archived_file_name = f"{combined_xml_file}_{timestamp}"
        archive_path = os.path.join(archive_folder, archived_file_name)
        if not os.path.exists(archive_folder):
            os.makedirs(archive_folder)
        shutil.move(combined_xml_file, archive_path)
        print(f"Archived old combined XML file as {archive_path}")

if __name__ == "__main__":
    # Load configuration from the YAML file
    config = load_config('config.yaml')
    
    # Define the temp folder
    temp_folder = 'temp'
    
    # Download and decompress the EPG files into the temp folder
    input_files = download_and_decompress_epg_files(config['epg_sources'], temp_folder)
    
    # Define filenames for combined XML and compressed .gz files
    combined_xml_file = "combined_epg.xml"
    compressed_gz_file = "combined_epg.xml.gz"
    
    # Archive old combined XML file if it exists
    archive_folder = 'archive'
    archive_old_combined_file(combined_xml_file, archive_folder)
    
    # Combine the downloaded files into a single XML file
    combined_xml = combine_epg_files(input_files, combined_xml_file)
    
    if combined_xml:
        # Compress the combined XML file to .gz
        compress_to_gz(combined_xml_file)
        
        # Upload both the compressed .gz and combined XML file to the GitHub repository
        upload_to_github(config['github']['repo_name'], [compressed_gz_file, combined_xml_file], config['github']['token'])
    
        # Clean up temporary files and folder
        cleanup_temp_folder(temp_folder)
