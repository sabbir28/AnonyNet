import os
import logging

# File paths
json_file_path = 'proxies/proxy_list.json'
sql_file_path = 'proxies/db/working_proxies.db'
csv_file_path = 'proxies/db/working_proxies.csv'

# List of file paths
file_paths = [json_file_path, sql_file_path, csv_file_path]

# Set up logging
log_file_path = 'logs/delete_files.log'
logging.basicConfig(
    filename=log_file_path,
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def delete_files(file_paths):
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logging.info(f"Deleted {file_path}")
                print(f"Deleted {file_path}")
            else:
                logging.warning(f"File not found: {file_path}")
                print(f"File not found: {file_path}")
        except Exception as e:
            logging.error(f"Error deleting {file_path}: {e}")
            print(f"Error deleting {file_path}: {e}")

if __name__ == "__main__":
    delete_files(file_paths)
