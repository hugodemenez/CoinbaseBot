try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import ConfigParser  # ver. < 3.0

# instantiate
config = ConfigParser()

key = 'ENTER YOUR PUBLIC KEY'
passphrase = 'ENTER YOUR PASSPHRASE'
b64secret = 'ENTER YOUR SECRET KEY'
api_url='https://api-public.sandbox.pro.coinbase.com'
exchange = 'COINBASE'
crypto= 'BTC'
currency_symbol = 'EUR'
risk = 'ENTER YOUR RISK'
stablecoin='EUR'
ROI='ENTER YOUR RETURN ON INVESTMENT'

# add a new section and some values
config.add_section('main')
config.set('main', 'key', key)
config.set('main', 'passphrase', passphrase)
config.set('main', 'b64secret', b64secret)
config.set('main', 'api_url', api_url)
config.set('main', 'exchange', exchange)
config.set('main', 'crypto', crypto)
config.set('main', 'currency_symbol', currency_symbol)
config.set('main', 'risk', risk)
config.set('main', 'stablecoin', stablecoin)
config.set('main', 'rendement', ROI)


# save to a file
with open('config.ini', 'w') as configfile:
    config.write(configfile)