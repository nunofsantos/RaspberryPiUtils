import ConfigParser
import logging
import smtplib


log = logging.getLogger(__name__)


def send_gmail(email_from, password, emails_to, subject, body):
    try:
        gmail = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        gmail.ehlo()
        gmail.login(email_from, password)
        email_text = '''\
From: {email_from}
To: {to}
Subject: {subject}

{body}
'''.format(email_from=email_from, to=emails_to, subject=subject, body=body)
        gmail.sendmail(email_from, emails_to, email_text)
        gmail.quit()
        log.debug('Email "{}" sent to {}'.format(subject, emails_to))
        return True
    except smtplib.SMTPException:
        return False


class ReadConfigMixin(object):
    @staticmethod
    def read_config():
        parser = ConfigParser.ConfigParser()
        parser.read('config.ini')
        config = {}
        type_conversion_map = {
            'STR': lambda x: str(x),
            'INT': lambda x: int(x),
            'FLOAT': lambda x: float(x),
            'BOOL': lambda x: x.lower() == 'true',
            'STRLIST': lambda x: (
                [elem.strip() for elem in value.strip('[], ').split(',')]
                if ',' in x
                else [str(x.strip('[], '))]
            ),
            'INTLIST': lambda x: (
                [int(elem.strip()) for elem in value.strip('[], ').split(',')]
                if ',' in x
                else [int(x.strip('[], '))]
            ),
        }
        for section in parser.sections():
            config[section] = {}
            for (key, value) in parser.items(section):
                key = key.upper()
                converted = False
                for t, func in type_conversion_map.iteritems():
                    if key.endswith('_{}'.format(t)):
                        key = key[:-(len(t)+1)]
                        try:
                            value = func(value)
                            converted = True
                        except ValueError:
                            converted = None
                            log.debug('Cannot convert value {} in key {}, ignoring'.format(value, key))
                        break
                if converted:
                    config[section][key] = value
                    log.debug('{} = {}'.format(key, value))
                elif converted is not None:
                    log.debug('Unrecognized type in key {}, ignoring'.format(key))
        return config
