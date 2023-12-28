import json
import os
import paramiko
import requests
import shutil
import uuid

from datetime import datetime
from tqdm import tqdm

# Generuje unikátní identifikátor (UUID)
def generate_uuid():
    return str(uuid.uuid4())

# Generuje metadata pro dokument na základě názvu souboru a UUID
def generate_metadata(filename, uuid):
    basename = os.path.basename(filename)
    return {
        "deleted": False,
        "lastModified": f"{int(datetime.now().timestamp())}000",
        "metadatamodified": False,
        "modified": False,
        "parent": "",
        "pinned": False,
        "synced": False,
        "type": "DocumentType",
        "version": 1,
        "visibleName": os.path.splitext(basename)[0],
}

# Generuje obsah pro dokument na základě přípony souboru
def generate_content(filename):
    extension = filename.split('.')[-1]
    content = {}
    
    if extension == 'pdf':
        content["fileType"] = "pdf"
    elif extension == 'epub':
        content["fileType"] = "epub"
    else:
        raise ValueError(f"Neznámý typ souboru: {extension}")
    
    return content

# Nahraje soubory do reMarkable pomocí protokolu SFTP
def upload_to_remarkable(local_directory, remote_directory, remarkable_ip, remarkable_username, remarkable_password):
    with paramiko.Transport((remarkable_ip, 22)) as transport:
        transport.connect(username=remarkable_username, password=remarkable_password)
        session = transport.open_channel(kind='session')
        session.settimeout(20)
        session.get_pty()
        sftp = paramiko.SFTPClient.from_transport(transport)
        
        total_files = sum([len(files) for _, _, files in os.walk(local_directory)])
        current_file = 0
        
        for root, dirs, files in os.walk(local_directory):
            for file in files:
                local_path = os.path.join(root, file)
                remote_path = os.path.join(remote_directory, os.path.relpath(local_path, local_directory))
                
                def callback(bytes_transferred, file_size):
                    pbar.update(bytes_transferred)
                
                with tqdm(total=os.path.getsize(local_path), unit='B', unit_scale=True, desc=f"Nahrávám soubory do reMarkable: {file}") as pbar:
                    sftp.put(local_path, remote_path, callback=callback)
                
                current_file += 1
                percentage = (current_file / total_files) * 100

# Restartuje službu xochitl na reMarkable
def restart_xochitl(remarkable_ip, remarkable_username, remarkable_password):
    with paramiko.SSHClient() as ssh:
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(remarkable_ip, port=22, username=remarkable_username, password=remarkable_password)
        ssh.exec_command("systemctl restart xochitl")
        print("Aplikace xochitl na reMarkable byla restartována.")
        print("Soubor se brzy zobrazí na vašem reMarkable.")

# Použití
url_path = input('Zadejte URL souboru: ')
file_name = input('Zadejte název souboru (včetně přípony): ')
remarkable_ip = input('Zadejte IP adresu reMarkable: ')
remarkable_username = 'root'
remarkable_password = input('Zadejte heslo reMarkable: ')
remarkable_path = '/home/root/.local/share/remarkable/xochitl'

# Generuje UUID, metadata a obsah dokumentu
uuid = generate_uuid()
metadata = generate_metadata(file_name, uuid)
content = generate_content(file_name)

# Vytvoří temporální adresář
tmpdir = f"/tmp/{uuid}"
os.makedirs(tmpdir)

# Stáhne soubor z URL a uloží do temporálního adresáře
response = requests.get(url_path, stream=True)

total_size = int(response.headers.get('content-length', 0))
block_size = 1024
with open(f"{tmpdir}/{uuid}.pdf", 'wb') as f, tqdm(
                                                   desc=f"Stahuji soubor z URL adresy: {file_name}.pdf",
                                                   total=total_size, unit='B', unit_scale=True,
                                                   unit_divisor=1024,
                                                   ) as pbar:
    for data in response.iter_content(block_size):
        pbar.update(len(data))
        f.write(data)

# Uloží metadata a obsah dokumentu do temporálního adresáře
with open(f"{tmpdir}/{uuid}.metadata", 'w') as f:
    json.dump(metadata, f)

with open(f"{tmpdir}/{uuid}.content", 'w') as f:
    json.dump(content, f)

# Nahraje soubory do reMarkable
upload_to_remarkable(tmpdir, remarkable_path, remarkable_ip, remarkable_username, remarkable_password)

# Odstraní temporální (dočasný) adresář
shutil.rmtree(tmpdir)
print("Temporální (dočasný) adresář byl odstraněn.")

# Restartuje aplikaci xochitl na reMarkable
restart_option = input('Chcete restartovat službu xochitl na reMarkable? (ano/ne): ').lower()

if restart_option in ['ano', 'a', 'yes', 'y']:

    restart_xochitl(remarkable_ip, remarkable_username, remarkable_password)
else:
    print("Restartování aplikace xochitl bylo přeskočeno.")
    print("Mějte na paměti, že soubory se na vašem reMarkable zobrazí až po restartu aplikace xochitl.")
