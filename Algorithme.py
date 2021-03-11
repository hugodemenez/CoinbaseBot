#!/usr/local/bin/python3
# -*- coding: UTF8 -*-
#Copyright : Hugo Demenez
#14_02_2021
#Private distribution

#Dans ce programme nous allons faire des echanges crypto/crypto, il est nécessaire de disposer d'une compte en stable coin (on l'appelle stablecoin dans le programme)
#Il faut initialiser le programme avec les informations dans le fichier config.ini, on indique le rendement souhaité (attention le risque est proportionnel) 
#Nous commencons le programme par chercher une cryptomonnaies qui aurait un potentiel à l'aide des outils de tradingview
#Ensuite on fait un echange vers cette crypto  (qu'on appelle crypto dans le programme)
#On suit le cours de cette crypto choisie et lorsque le rendement est atteint, on effectue un echange vers le stable coin

import cbpro, time, requests,json,os,math,datetime
from tradingview_ta import TA_Handler, Interval
from configparser import ConfigParser

#Fichier où la configuration est enregistrée
config = ConfigParser()
config.read(r'config.ini')

#On configure l'api
key = config.get("main","key")
passphrase = config.get("main","passphrase")
b64secret = config.get("main","b64secret")
api_url=config.get("main","api_url")

#Authentification
auth_client = cbpro.AuthenticatedClient(key, b64secret, passphrase,api_url=api_url)
public_client = cbpro.PublicClient()

#On configure le programme avec le fichier config.ini
exchange = config.get("main","exchange")
crypto = config.get("main","crypto") #ex: ETH
stablecoin = config.get("main","stablecoin") #ex: USDC
symbol = crypto+stablecoin #ex: ETHEUR
product_id= crypto+'-'+stablecoin #ex: ETH-USDC
risk = float(config.get("main","risk")) #Risque toléré avant la vente
rendement=float(config.get("main","rendement")) #Le rendement va fermer les positions lorsque le rapport sera atteint

#Fonction pour faire une troncature, la fonction round fait un arrondi (probleme lorsque l'on dispose de 499.997€ par exemple)
def truncate(number, decimals=0):
    """
    Returns a value truncated to a specific number of decimal places.
    """
    if not isinstance(decimals, int):
        raise TypeError("decimal places must be an integer.")
    elif decimals < 0:
        raise ValueError("decimal places has to be 0 or more.")
    elif decimals == 0:
        return math.trunc(number)
    factor = 10.0 ** decimals
    return math.trunc(number * factor) / factor

#On definit cette classe pour pouvoir recuperer les informations du compte
class Balance():
    def __init__(self):
        #Regarder dans les informations du compte pour avoir l'adresse du portefeuille et le capital
        for currency in auth_client.get_accounts():
            if currency['currency']==stablecoin:
                self.stablecoin = float(truncate(float(currency['balance']),2))
            if currency['currency']==crypto:
                self.crypto= float(currency['balance'])

#On definit une classe pour la position
class Position():
    def __init__(self):
        self.information='close'
        self.buy_price = 0
        self.fee = 0
        self.sell_price=0
        self.size=0
        self.plus_haut =0.0
        self.id =''
        self.funds=0.0
        self.nb_position=0
        self.nb_win=0
        self.nb_loss=0
        self.id_takeprofit=''

#On definit une variable position qui sera utilisée globalement
Position = Position()

class Indicator():
    def __init__(self):
        self.movement='stable'
        self.last_value=0.0
        self.value=0.0

#On definit trois indicateurs
StochK=Indicator()
StochD=Indicator()
EMA_200=Indicator()

#Cette fonction est une fonction qui permet d'obtenir des signaux d'entrée par rapport à des analyses techniques
def get_side_info():
        #On paramètre la lecture des analyses qui sont fournies par TradingView
    handler  = TA_Handler()
    handler.set_symbol_as(symbol)
    handler.set_exchange_as_crypto_or_stock(exchange)
    handler.set_screener_as_crypto()
    #On choisi de regarder le marché sur 15 minutes
    handler.set_interval_as(Interval.INTERVAL_15_MINUTES)
    #On recupere les données des analyses techniques et du marché
    try:
        analyse=handler.get_analysis()
    except:
        #Si l'analyse echoue alors on considere que l'on a pas eu de signal d'entrée
        return 'sell'
    #Ma méthode d'analyse
    #Cette methode est une methode de scalping présentée par Guillaume Graf, trader indépendant. Il utilise le stochastique et la moyenne exponentielle 200 periodes.
    #Il faut une prise de benef à 1% et un stop garanti tres faible puisque cette methode traduit un retournement vers la hausse très rapide. Si on chute alors le signal est défectueux
    #On peut donc mettre des pertes à 0,2 ou 0,3% et une prise de benef à 1%.
    StochK.value=analyse.indicators['Stoch.K']
    EMA_200.value=analyse.indicators['EMA200']
    current_price=Price().buy
    if StochK.value<18.0 and current_price<EMA_200.value*0.99:
        for resistance in analyse_resistances():
            if current_price<(float(resistance)*1.005) and current_price>(float(resistance)):
                return 'buy'
    else:
        return 'sell'

def analyse_resistances():
    resistances=[]
    with open("resistances.txt") as f:
        for line in f:
            line = str.strip(line)
            resistances.append(line)

    resistances.sort()
    resistances.remove(resistances[0])
    resistances.remove(resistances[len(resistances)-1])
    return resistances

#Fonction pour enregistrer du texte dans un fichier .txt
def save_order(texte):
    fichier_text = open("Ordres.txt","a") 
    fichier_text.write(texte+'\n')
    fichier_text.close() 

#Fonction qui gere les actions de l'algorithme et l'ouverture d'ordre (on pourrait faire une fonction pour ouvrir des ordres)
def trading():
    #Si on peut acheter et que nous ne l'avons pas encore fait
    if Position.information=='close':
        order_side=get_side_info()
        if order_side =='buy':
            print("L'indicateur nous dit d'acheter")
            #On crée un ordre d'achat en fermant toutes les positions deja ouvertes
            create_order()
    else:
        #On regarde l'etat du takeprofit. Si il est done alors on indique au programme que la position est fermée
        if auth_client.get_order(Position.id_takeprofit)['status'] == 'done':
            print('On a vendu la position')
            #On indique que la position est fermée
            Position.information='close'
            Position.nb_win+=1
        
#Cette fonction gère les ordres
def create_order():
    order = auth_client.place_market_order(product_id=product_id, side='buy',  funds=Balance().stablecoin)
    #On met la position comme ouverte si l'ordre s'est bien passé
    try :
        #Si le message existe alors il y a une erreur
        type(order['message']) == str
        print("Il y a une erreur : "+order['message'])
    except:
        #On stock l'identifiant de l'ordre pour pouvoir faire un suivi
        Position.id = order['id']
        #Tant que notre ordre n'est pas validé, on attend, car il nous faut les infos
        timout=0
        while(True):
            try:
                #Fills est le resumé de l'ordre qui a été accepté par le marché
                fills = list(auth_client.get_fills(order_id=Position.id))[0]
                break
            except:
                timout+=1
                if timout%300==0:
                    print("L'ordre n'a pas été reçu par le marché")
                    #On doit peut etre annuler l'ordre au risque qu'il passe à un moment... 
                    auth_client.cancel_order(Position.id)
                    #On sort de la fonction pour repasser un ordre
                    return
                pass
        print('La position est ouverte')
        #On stock la quantité achetée
        Position.size = float(fills['size'])
        #On indique qu'on a une position ouverte
        Position.information='open'
        #On stock l'information du prix d'achat
        Position.buy_price=float(fills['price'])
        #On stock les frais 
        Position.fee=round(float(fills['fee']),2)
        #On stock le prix le plus haut comme prix d'achat
        Position.plus_haut=float(Position.buy_price)
        #On enregistre le nombre de positions
        Position.nb_position+=1
        #On enregistre l'ordre dans un fichier texte
        save_order(str(order))
        #On place également un takeprofit, on regardera le flag de sortie pour pouvoir repasser un ordre (quand la limite est totalement remplie on peut considerer la position comme fermée)
        order = auth_client.place_limit_order(product_id=product_id, side='sell', price=truncate(Position.buy_price*rendement,2) , size=Position.size)
        try :
            #Si le message existe alors il y a une erreur
            type(order['message']) == str
            print("Il y a une erreur : "+order['message'])
        except:
            #On stock l'identifiant de l'ordre pour pouvoir faire un suivi
            Position.id_takeprofit = order['id']
            
            

#Price permet d'obtenir les prix pour l'actif à trader
class Price:
    def __init__(self):
        response = requests.get('https://api.pro.coinbase.com/products/'+product_id+'/book')
        response = response.json()
        self.sell=float(response['bids'][0][0])
        self.buy=float(response['asks'][0][0])


#On se reconnecte au service CoinBase et on actualise les configurations
def connexion_refresh():
    global auth_client,public_client,exchange,crypto,stablecoin,symbol,product_id,risk,rendement
    #Authentification
    auth_client = cbpro.AuthenticatedClient(key, b64secret, passphrase,api_url=api_url)
    public_client = cbpro.PublicClient() 
    #On configure le programme avec le fichier config.ini
    exchange = config.get("main","exchange")
    crypto = config.get("main","crypto") #ex: ETH
    stablecoin = config.get("main","stablecoin") #ex: USDC
    symbol = crypto+stablecoin #ex: ETH-USDC
    product_id= crypto+'-'+stablecoin #ex: ETH-USDC
    risk = float(config.get("main","risk"))
    rendement=float(config.get("main","rendement")) #Le rendement va fermer les positions lorsque le rapport sera atteint

#Boucle de programme
def main():
    #On initialise le temps de fonctionnement du programme
    start_time = time.time()
    print('Starting Trading:')
    up_time=0
    while(True):
        try:
            trading()
            #On ralenti le programme pour ne pas avoir trop de requetes vers les serveurs (risque d'etre deconnecté)
            time.sleep(1)
            up_time+=1
            if up_time%60==0:
                #Il faut actualiser la connexion pour ne pas etre déconnecté
                connexion_refresh()
                if up_time%3600==0:
                    print('Le programme fonctionne depuis %s'%str(datetime.timedelta(seconds=round(time.time(),0)-round(start_time,0))))
                    #On fait un résumé de la performance
                    print("On a effectué %s opérations"%str(Position.nb_win))
                    #On redemarre le compteur pour ne pas risquer d'avoir une erreur si le temps est trop elevé.
                    up_time=0
        #Si on essaie de fermer le programme avec une combinaison clavier
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    main()