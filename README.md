# nagios-agent

Email reflector for low-bandwidth SMS-only clients such as satphone that do not allow web or frequent email 
(simply configuring Nagios to send alerts to a satphone SMS mail alias will typically result in the sender or 
mailbox being blacklisted by the provider for exceeding rate limits). Allows the user to request current 
Nagios status by sending a special SMS which causes the reflector to send a reply. 

Works by checking a designated IMAP mailbox for the special email sent from the handset via SMS.
Upon receipt of the special email Nagios is checked by scraping the web UI and a 
response email sent by SMTP.

