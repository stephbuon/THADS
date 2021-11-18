import io
import json
import os
import re
from typing import Optional

import requests
from PIL import Image
from hathitrust_api.data_api import DataAPI
from internetarchive import search_items, get_item, download

HATHI_ACCESS_KEY = os.environ.get('HATHI_ACCESS_KEY', '')
HATHI_SECRET_KEY = os.environ.get('HATHI_SECRET_KEY', '')

output_directory = os.environ.get('SCRATCH', '')

if output_directory:
    output_directory += '/hathi/'
else:
    output_directory = './hathi/'


class InternetArchiveFormats:
    PDF = 'Text PDF'
    TXT = 'DjVuTXT'


def download_all_archive(format: str):
    for result in search_items('creator:"American Institute of the City of New York"'):
        identifier = result['identifier']
        item = get_item(identifier)
        metadata = item.item_metadata
        title = metadata['metadata']['title']
        date = metadata['metadata']['date']

        title = title.lower().strip()

        if 'annual report' not in title and 'transaction' not in title:
            continue

        print(identifier)
        print('\t', title)
        print('\t', date)

        download(identifier, formats=[format, ], ignore_existing=True)


def check_file_for_date(filepath: str):
    with open(filepath, 'r') as f:
        for _ in range(80):
            line = f.readline()
            match = re.search(r'\b1[89][0-9][0-9]\b', line) # type: Optional[re.Match]
            if match is not None:
                return line
    return None


def fetch_ocr(item: dict, hathi_api):
    item_id = item['htid']
    year = item['enumcron']
    filename = 'annual_report_for_' + year.replace('/', '_') + '.txt'
    print('Fetching OCR for item:', item_id, '(', year, ')')
    pages = hathi_api.getdocumentocr(item_id)
    print('Writing to file...')

    with open('hathi/' + filename, 'w+') as f:
        for page in pages:
            f.write(page.decode('utf-8'))
            f.write('\n')


def fetch_pdf(item: dict, hathi_api):
    item_metadata = json.loads(hathi_api.getmeta(item['htid'], json=True).decode('utf-8'))
    item_id = item['htid']
    num_pages = int(item_metadata['htd:numpages'])
    if not num_pages:
        print('No pages found.')
        return
    year = item['enumcron']
    filename_base = 'annual_report_for_' + year.replace('/', '_')
    output_filepath = f'{output_directory}/{filename_base}.pdf'
    if os.path.isfile(output_filepath):
        print('skipping:', filename_base)
        return

    images_list = []
    for i in range(num_pages):
        print('Fetching page %d out of %d' % (i + 1, num_pages))
        image_data = hathi_api.getpageimage(item_id, i + 1)
        image = Image.open(io.BytesIO(image_data))
        images_list.append(image)

    images_list[0].save(output_filepath, save_all=True, append_images=images_list[1:])


def get_record_metadata(record_number: str):
    url = f'https://catalog.hathitrust.org/api/volumes/full/recordnumber/{record_number}.json'
    response = requests.get(url)
    return response.json()


def download_all_hathi():
    if not os.path.exists('hathi'):
        os.mkdir('hathi')

    metadata = get_record_metadata('008163759')

    hathi_api = DataAPI(client_key=HATHI_ACCESS_KEY, client_secret=HATHI_SECRET_KEY)

    for item in metadata['items']:
        fetch_pdf(item, hathi_api)
        # fetch_ocr(item, hathi_api)


if __name__ == '__main__':
    download_all_hathi()
