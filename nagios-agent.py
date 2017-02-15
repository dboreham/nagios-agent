# Connect to IMAP and check for unread email in the inbox.
# Check each new email to see if it is one of interest to us
# If so then process it and reply with a summary of the current
# nagios status

import imaplib
import smtplib
import email
import bs4
import requests
import time
import traceback
import sys

nagios_url = r'http://monitoring.nuevasync.com:9857/nagios/cgi-bin//status.cgi'
nagios_username = 'nagiosadmin'
nagios_password = 'xxxxxxxx'

imap_host = 'mail.example.com'
imap_port = 993
imap_username = 'nagios-check@example.com'
imap_password = 'xxxxxxxx'
smtp_host = imap_host
smtp_port = 25
smtp_auth = True

# Incoming message subject strings need to be lower case
# We include the empty string because AT&T's SMS gateway sends emails with no subject
request_subjects = ['via inmarsat:', 'check', '']
response_from = 'nagios-check@bozemanpass.com'
response_subject = 'Nagios Check'

check_interval = 60 * 1


def send_response_email(message_recipient, message_text):
    message = email.message.Message()
    message['From'] = response_from
    message['To'] = message_recipient
    message['Subject'] = response_subject
    message.set_payload(message_text)
    session = smtplib.SMTP(smtp_host)
    try:
        if smtp_auth:
            session.login(imap_username, imap_password)
        session.send_message(message, response_from, message_recipient)
    finally:
        session.close()


def check_mailbox():
    """
    :return: The sender for any unread email that matches our criteria
    """
    retval = None
    # Open an IMAP connection
    imap_connection = imaplib.IMAP4_SSL(imap_host, imap_port)
    try:
        status, result = imap_connection.login(imap_username, imap_password)
        if status == 'OK':
            # Now get the inbox
            status, result = imap_connection.select('INBOX', readonly=False)
            status, result = imap_connection.search(None, '(UNSEEN)')
            for msg_num in result[0].split():
                if not(msg_num):
                    continue
                data = imap_connection.fetch(msg_num, '(BODY.PEEK[HEADER])')
                # Decode the header. The subscripts in the following line
                # are a demonstration of the power of untyped languages <cough>
                message = email.message_from_bytes(data[1][0][1])
                sender = message['from']
                subject = message['subject']
                if subject.lower() in request_subjects:
                    # We have a winner
                    # We're going to optimistically mark it as read since we aren't doing
                    # financial transactions here and it would be more complicated to come back
                    # and mark the message read later
                    imap_connection.store(msg_num,'+FLAGS','\Seen')
                    # Bail out on the first hit. We will come back later for any subsequent messages
                    retval = sender
                    break
        else:
            print('Failed to login to mailbox: ' + str(result))
    finally:
        try:
            imap_connection.close()
        except:
            pass
        imap_connection.logout()
    return retval


def get_status_from_service_name(soup, service_name):
    # Find the a tag for this service
    atags = soup.find_all('a', text=service_name)
    if len(atags) != 1:
        print('Something went wrong')
    atag = atags[0]
    # Now navigate from this tag to the one we are interested in
    statustag = atag.parent.parent.parent.parent.parent.parent.parent.next_sibling.next_sibling
    statustext = statustag.get_text()
    return statustext


def get_nagios_summary():
    result = 'Unexpected Error'
    nagios_params = {'host': 'all'}
    page_response = requests.get(nagios_url, params=nagios_params, auth=(nagios_username, nagios_password))
    if page_response.status_code == requests.codes.ok:
        page_content = page_response.text
        soup = bs4.BeautifulSoup(page_content)
        atags = soup.select('table > tr > td a')
        # We need to pick out the elements that have the string 'type=2' in the href attribute since those are the
        # services (as opposed to the hosts).
        service_names = [e.get_text() for e in atags if r'type=2&host=' in e.attrs['href'] and e.get_text() != '']
        # for each service, navigate from the element containing the service name to its status
        # Status will have the value 'OK' or 'CRITICAL'
        statuses = [get_status_from_service_name(soup, s) for s in service_names]
        # Now zip them together into a list of tuples
        services_statuses = list(zip(service_names, statuses))
        ok_count = 0
        not_ok_count = 0
        not_ok_list = []
        for x in services_statuses:
            if x[1] == 'OK':
                ok_count += 1
            else:
                not_ok_count += 1
                not_ok_list.append(x[0])
        result = 'Services ok: ' + str(ok_count)
        if not_ok_count > 0:
            result = result + '\nServices not ok: ' + ','.join(not_ok_list)
    else:
        result = 'Error fetching page'
    return result


if __name__ == '__main__':
    while True:
        try:
            sender = check_mailbox()
            last_check_time = time.time()
            if sender:
                print('Got this sender: ' + sender)
                nagios_summary = get_nagios_summary()
                send_response_email(sender, nagios_summary)
            else:
                print('Found nothing this time')
        except Exception:
            print('Caught exception:\n' + traceback.format_exc(), file=sys.stderr)
        # Wait until it is time to check again
        while time.time() < last_check_time + check_interval:
            time.sleep(1)
