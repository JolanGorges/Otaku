import re
import json
from resources.lib.ui import source_utils, client, control
from resources.lib.ui.BrowserBase import BrowserBase
from resources.lib.debrid import real_debrid, premiumize, all_debrid, torbox
import threading


class sources(BrowserBase):
    def __init__(self):
        self.cloud_files = []
        self.threads = []

    def get_sources(self, debrid, query, episode, media_type):
        if debrid.get('real_debrid'):
            self.threads.append(
                threading.Thread(target=self.rd_cloud_inspection, args=(query, episode, media_type,)))

        if debrid.get('premiumize'):
            self.threads.append(
                threading.Thread(target=self.premiumize_cloud_inspection, args=(query, episode,)))

        if debrid.get('all_debrid'):
            self.threads.append(
                threading.Thread(target=self.alldebrid_cloud_inspection, args=(query, episode,)))

        if debrid.get('torbox'):
            self.threads.append(
                threading.Thread(target=self.torbox_cloud_inspection, args=(query, episode,)))

        for i in self.threads:
            i.start()

        for i in self.threads:
            i.join()

        return self.cloud_files

    def rd_cloud_inspection(self, query, episode, media_type):
        api = real_debrid.RealDebrid()
        torrents = api.list_torrents()

        filenames = [re.sub(r'\[.*?\]\s*', '', i['filename']) for i in torrents]
        filenames_query = ','.join(filenames)
        resp = client.request('https://armkai.vercel.app/api/fuzzypacks', params={"dict": filenames_query, "match": query})
        resp = json.loads(resp)

        for i in resp:
            torrent = torrents[i]
            filename = re.sub(r'\[.*?]', '', torrent['filename']).lower()
            if source_utils.is_file_ext_valid(filename) and media_type != 'movie' and ('-' not in filename or str(episode) not in filename.rsplit('-', 1)[1]):
                continue
            torrent_info = api.torrentInfo(torrent['id'])

            torrent_files = [selected for selected in torrent_info['files'] if selected['selected'] == 1]
            if not any(source_utils.is_file_ext_valid(tor_file['path'].lower()) for tor_file in torrent_files):
                continue

            if control.getSetting('general.manual.select') != 'true':
                best_match = source_utils.get_best_match('path', torrent_files, str(episode))
                for f_index, torrent_file in enumerate(torrent_files):
                    if torrent_file['path'] == best_match['path'] if best_match else True:
                        self.cloud_files.append(
                            {
                                'quality': source_utils.getQuality(torrent['filename']),
                                'lang': source_utils.getAudio_lang(torrent['filename']),
                                'hash': torrent_info['links'][f_index],
                                'provider': 'Cloud',
                                'type': 'cloud',
                                'release_title': torrent_file['path'][1:],
                                'info': source_utils.getInfo(torrent['filename']),
                                'debrid_provider': 'real_debrid',
                                'size': self._get_size(torrent_file['bytes']),
                                'torrent_files': None
                            }
                        )
                        break
            else:
                self.cloud_files.append(
                    {
                        'quality': source_utils.getQuality(torrent['filename']),
                        'lang': source_utils.getAudio_lang(torrent['filename']),
                        'hash': torrent_info['links'],
                        'provider': 'Cloud',
                        'type': 'cloud',
                        'release_title': torrent['filename'],
                        'info': source_utils.getInfo(torrent['filename']),
                        'debrid_provider': 'real_debrid',
                        'size': self._get_size(torrent['bytes']),
                        'torrent': torrent,
                        'torrent_files': torrent_files,
                        'torrent_info': torrent_info,
                        'episode': episode
                    }
                )

    def premiumize_cloud_inspection(self, query, episode):
        cloud_items = premiumize.Premiumize().list_folder('')

        filenames = [re.sub(r'\[.*?\]\s*', '', i['name']) for i in cloud_items]
        filenames_query = ','.join(filenames)
        resp = client.request('https://armkai.vercel.app/api/fuzzypacks', params={"dict": filenames_query, "match": query})
        resp = json.loads(resp)

        for i in resp:
            torrent = cloud_items[i]
            filename = re.sub(r'\[.*?\]', '', torrent['name']).lower()

            if torrent['type'] == 'file' and source_utils.is_file_ext_valid(filename):
                if episode in filename.rsplit('-', 1)[1]:
                    self._add_premiumize_cloud_item(torrent)
                else:
                    continue

            torrent_folder = premiumize.Premiumize().list_folder(torrent['id'])
            identified_file = source_utils.get_best_match('name', torrent_folder, episode)
            self._add_premiumize_cloud_item(identified_file)

    def _add_premiumize_cloud_item(self, item):
        self.cloud_files.append({
            'quality': source_utils.getQuality(item['name']),
            'lang': source_utils.getAudio_lang(item['name']),
            'hash': item['link'],  # premiumize.Premiumize()._fetch_transcode_or_standard(item),
            'provider': 'Cloud',
            'type': 'cloud',
            'release_title': item['name'],
            'info': source_utils.getInfo(item['name']),
            'debrid_provider': 'premiumize',
            'size': self._get_size(int(item['size']))
        })

    def alldebrid_cloud_inspection(self, query, episode):
        api = all_debrid.AllDebrid()
        torrents = api.list_torrents()['links']

        filenames = [re.sub(r'\[.*?]\s*', '', i['filename']) for i in torrents]
        filenames_query = ','.join(filenames)
        resp = client.request('https://armkai.vercel.app/api/fuzzypacks', params={"dict": filenames_query, "match": query})
        resp = json.loads(resp)

        for i in resp:
            torrent = torrents[i]
            filename = re.sub(r'\[.*?]', '', torrent['filename']).lower()
            if source_utils.is_file_ext_valid(filename) and episode not in filename.rsplit('-', 1)[1]:
                continue

            torrent_info = api.link_info(torrent['link'])
            torrent_files = torrent_info['infos']

            if len(torrent_files) > 1 and len(torrent_info['links']) == 1:
                continue

            if not any(source_utils.is_file_ext_valid(tor_file['filename'].lower()) for tor_file in torrent_files):
                continue

            url = api.resolve_hoster(torrent['link'])
            self.cloud_files.append(
                {
                    'quality': source_utils.getQuality(torrent['filename']),
                    'lang': source_utils.getAudio_lang(torrent['filename']),
                    'hash': url,
                    'provider': 'Cloud',
                    'type': 'cloud',
                    'release_title': torrent['filename'],
                    'info': source_utils.getInfo(torrent['filename']),
                    'debrid_provider': 'all_debrid',
                    'size': self._get_size(torrent['size']),
                    'episode': episode
                }
            )

    def torbox_cloud_inspection(self, query, episode):
        api = torbox.Torbox()
        torrents = api.list_torrents()

        filenames = [re.sub(r'\[.*?\]\s*', '', i['name']) for i in torrents]
        filenames_query = ','.join(filenames)
        resp = client.request('https://armkai.vercel.app/api/fuzzypacks', params={"dict": filenames_query, "match": query})
        resp = json.loads(resp)

        for i in resp:
            torrent = torrents[i]
            if torrent['cached'] is not True or torrent['download_finished'] is not True:
                continue

            if len(torrent['files']) <= 0:
                continue

            if not any(source_utils.is_file_ext_valid(tor_file['name'].lower()) for tor_file in torrent['files']):
                continue

            file = source_utils.get_best_match('short_name', torrent['files'], episode)
            if file and file['id'] is not None:
                url = api.request_dl_link(torrent['id'], file['id'])
                self.cloud_files.append(
                    {
                        'quality': source_utils.getQuality(file['name']),
                        'lang': source_utils.getAudio_lang(file['name']),
                        'hash': url,
                        'provider': 'Cloud',
                        'type': 'cloud',
                        'release_title': torrent['name'],
                        'info': source_utils.getInfo(file['name']),
                        'debrid_provider': 'torbox',
                        'size': self._get_size(int(torrent['size'])),
                        'episode': episode
                    }
                )
