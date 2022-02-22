import discord
from discord.ext import tasks
import matplotlib.pyplot as plt
from pycoingecko import CoinGeckoAPI
import pandas as pd
from datetime import datetime
import uuid
import pathlib
import os

cg = CoinGeckoAPI()
client = discord.Client()
current_directory = pathlib.Path(__file__).parent.resolve()

async def search_by_ID(id):
    return next((item for item in coins_list if item['id'].lower() == id.lower()), False)

async def search_by_symbol(symbol):
    return next((item for item in coins_list if item['symbol'].lower() == symbol.lower()), False)

def update_coins_list():
    global coins_list
    coins_list = cg.get_coins_list()

def get_crypto_chart(token):
    chart_data = cg.get_coin_market_chart_by_id(id=f'{token}', vs_currency='usd', days='7')
    UUID = uuid.uuid4()
    images_dir = os.path.join(current_directory, "images")
    if not (os.path.isdir(images_dir)):
        os.makedirs(images_dir)
        print ("created directory: " + images_dir)
    filename = os.path.join(images_dir, str(UUID)+".png")

    def unix_to_date(unix_time):
        timestamp = datetime.fromtimestamp((unix_time/1000))
        return f"{timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

    new_data = {}

    for each in chart_data['prices']:
        date = unix_to_date(each[0])
        new_data[date] = each[1]

    df = pd.DataFrame({'Dates': new_data.keys(), 'Prices': new_data.values()})
    #print(df.head())

    df.plot(x ='Dates', y='Prices', kind = 'line', legend = None)
    
    plt.title(f'7-day historical market price of {token}', fontsize=15, color= 'white', fontweight='bold')
    plt.xticks(rotation=45, color='white')
    plt.yticks(color='white')
    plt.savefig(filename, transparent=True, bbox_inches="tight")
    plt.close()
    return filename

async def send_coin_message(coin_name, message):
    checking_message = await message.channel.send("Checking...")

    symbol_search_result = await search_by_symbol(coin_name)
    if symbol_search_result is False:
        id_search_result = await search_by_ID(coin_name)
        if id_search_result is False:
            await checking_message.edit(content="Could not find coin by ID or symbol")
            pass
        else:
            coin_object = Coin(id_search_result['id'])
            #print(f"Found this coin by ID: {id_search_result['name']}")
    else:
        coin_object = Coin(symbol_search_result['id'])
        #print(f"Found this coin by symbol: {symbol_search_result['name']}")

    #### Create the embed object ####
    embed = discord.Embed(title=f"{coin_object.coin_name}")
    embed.set_author(name=f"{client.user.name}", icon_url=client.user.avatar_url)
    embed.set_thumbnail(url=f"{coin_object.coin_image}")
    embed.add_field(name="Current Price 💵", value=coin_object.coin_price, inline=True)
    embed.add_field(name="Circulating Supply 🪙", value= coin_object.coin_circulating_supply, inline=True)
    embed.add_field(name="Market Cap 🤑", value= f"${coin_object.coin_market_cap}", inline=True)
    embed.add_field(name="24h-High ⬆️", value= coin_object.coin_high_24h, inline=True)
    embed.add_field(name="24h-low ⬇️", value= coin_object.coin_low_24h, inline=True)
    embed.add_field(name="Price Change 24h ⏰", value= coin_object.coin_price_change_percent, inline=True)
    embed.add_field(name="All Time High 👑", value= coin_object.coin_ath_price, inline=True)
    embed.add_field(name="ATH Percent Change 📊", value= coin_object.coin_ath_change_percent, inline=True)
    embed.add_field(name="ATL 😢", value = coin_object.coin_atl, inline=True)
    
    image_path = get_crypto_chart(coin_object.name)
    file = discord.File(image_path, filename="image.png")
    embed.set_image(url="attachment://image.png")

    await message.channel.send(file=file, embed=embed)
    await checking_message.delete()

    try:
        os.remove(image_path)
    except OSError as e:
        print ("Error deleting file: %s - %s." % (e.filename, e.strerror))

class Coin:
    def __init__(self, name):
        self.name = name.lower()
        self.coin_data = cg.get_coins_markets(vs_currency='usd', ids=f'{self.name}')
        self.coin_name = self.coin_data[0]['name']
        self.coin_image = self.coin_data[0]["image"]
        self.coin_price = "${:,}".format(self.coin_data[0]['current_price'])
        self.coin_circulating_supply = "{:,}".format(self.coin_data[0]["circulating_supply"])
        self.coin_market_cap = "{:,}".format(self.coin_data[0]['market_cap'])
        self.coin_high_24h = "${:,}".format(self.coin_data[0]['high_24h'])
        self.coin_low_24h = "${:,}".format(self.coin_data[0]['low_24h'])
        self.coin_price_change_percent = "{:,}%".format(round(self.coin_data[0]['price_change_percentage_24h'], 2))
        self.coin_ath_price = "${:,}".format(self.coin_data[0]["ath"])
        self.coin_ath_change_percent = "{:,}%".format(self.coin_data[0]["ath_change_percentage"])
        self.coin_atl = "${:,}".format(self.coin_data[0]["atl"])

@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))
    check_rates.start()
    coins_list_task.start()

@tasks.loop(minutes=1)
async def check_rates():
    await client.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching, 
            name="BTC @ $" + str(cg.get_price(ids="bitcoin", vs_currencies="usd")['bitcoin']['usd'])
        )
    )

#Update coins list once per day
@tasks.loop(minutes=1440)
async def coins_list_task():
    update_coins_list()

@client.event
async def on_message(message):
    # Converts user's input into a lowercase form
    #message.content = message.content.lower().replace(' ', '')
    message.content = message.content.lower()
    
    if message.author == client.user:
        return

    if message.content.startswith("$help"):
        await message.channel.send("""
To get the price of your chosen coin/token, simply place '$' before the abbreviated name of your token. For example: $eth
You can also enter the full name of the coin. For example: $etherium

List of available commands:
$trending
$market_dominance""")
        return

    if message.content.startswith("$trending"):
        trending_data = cg.get_search_trending()
        trending_tokens = []
        count_1 = 1
        for each in trending_data["coins"]:
            item = each["item"]["name"]
            trending_tokens.append(f"({count_1}). {item} \n")
            count_1 += 1
        trending_coins = ''.join(trending_tokens)

        await message.channel.send(f"Top 7 trending search coins\n-------------------------------------\n{trending_coins}")
        return

    if message.content.startswith("$market_dominance"):
        market_percent_data = cg.get_global()
        market_cap_percentage = []
        count_2 = 1
        for k, v in market_percent_data["market_cap_percentage"].items():
            market_cap_percentage.append(f"({count_2}). {k}: {round(v, 2)}% \n")
            count_2 += 1
        market_dom = ''.join(market_cap_percentage)

        await message.channel.send(f"Market Cap Percentage\n-------------------------------------\n{market_dom}")
        return

    if message.content.startswith('$'):
        await send_coin_message(message.content[1:], message)
        return

client.run("token")