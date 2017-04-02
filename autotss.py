import requests as r
import subprocess
import dataset
import os

def get_device_board(identifier): # Returns the board config given a device identifier
    api = r.get('https://api.ipsw.me/v2.1/firmwares.json/condensed')
    return api.json()['devices'][identifier]['BoardConfig']

def save_blobs(identifier, board_config, ecid, version): # Save shsh2 blobs with tsschecker
    save_path = os.path.dirname(os.path.realpath(__file__)) + "/blobs/" + identifier + "/" + ecid + "/" + version

    if not os.path.exists(save_path):
        os.makedirs(save_path)

    output = subprocess.Popen(['./tsschecker', '-e', ecid, '--boardconfig', board_config, '-i', version, '-s', '--save-path', save_path], stdout=subprocess.PIPE)

    if "Saved shsh blobs!" in output.stdout.read():
        print "Successfully saved blobs for " + identifier + " on " + version + ' with ECID: ' + ecid + "!"
        return True
    else:
        print "Error saving blobs for " + identifier + " on " + version + ' with ECID: ' + ecid + "!"
        return False

def check_for_devices(): # Check for new entries in devices.txt and add them to the database
    print "Checking for new devices to add to database..."

    with open('devices.txt') as f:
        for line in f:
            device_info, ecid = line.strip().split(':')
            try:
                identifier, board_config = device_info.split('-')
            except ValueError:
                identifier = device_info
                board_config = get_device_board(identifier)

            db = dataset.connect('sqlite:///devices.db')

            blobs_db = db['blobs']
            if blobs_db.find_one(ecid=ecid) is None:
                blobs_db.insert_ignore(dict(identifier=identifier, board_config=board_config, ecid=ecid, versions_saved=''), ['ecid'])
                print "Added - ID: " + identifier + ", ECID: " + ecid + ", Board Config: " + str(board_config)
def main():
    check_for_devices()

    db = dataset.connect('sqlite:///devices.db')

    blobs_db = db['blobs']
    api_db = db['api']
    api_db.insert_ignore(dict(field='md5', value=''), ['field'])
    api_db.insert_ignore(dict(field='num_devices', value=''), ['field'])

    api = r.get('https://api.ipsw.me/v2.1/firmwares.json/condensed')

    print "\nChecking for new signed firmwares or new added devices..."
    if (api.headers['content-md5'] != api_db.find_one(field='md5')['value']) or (str(blobs_db.count()) != api_db.find_one(field='num_devices')['value']):
        if str(blobs_db.count()) != api_db.find_one(field='num_devices')['value']:
            print "New devices found, checking for signed firmwares..."

        if (api.headers['Content-Md5'] != api_db.find_one(field='md5')['value']):
            print "New signed firmwares found...\n"

        for row in blobs_db.find():
            versions_saved = row['versions_saved'].split(',')
            for firmware in api.json()['devices'][row['identifier']]['firmwares']:
                if firmware['signed']:
                    if firmware['version'] not in versions_saved:
                        print "Attempting to save blobs for " + row['identifier'] + " on " + firmware['version'] + ' with ECID: ' + row['ecid'] + "..."
                        saved_blobs = save_blobs(row['identifier'], row['board_config'], row['ecid'], firmware['version'])
                        if saved_blobs:
                            blobs_db.update(dict(ecid=row['ecid'], versions_saved=row['versions_saved'] + firmware['version'] + ','), ['ecid'])

        api_db.update(dict(field='md5', value=api.headers['content-md5']), ['field'])
        api_db.update(dict(field='num_devices', value=str(blobs_db.count())), ['field'])
    else:
        print "No new blobs to be saved...nothing to do here."

if __name__ == "__main__":
    main()