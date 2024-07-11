import discord
from discord.ext import commands
from discord_interactions import DiscordInteractions
from discord_interactions import InteractionContext
import threading

# Replace these with your bot tokens
TOKEN1 = 'TOKEN1'
TOKEN2 = 'TOKEN2'

# Intents for the first bot
intents = discord.Intents.default()
intents.messages = True

# First bot using message intents
class Bot1(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'{self.bot.user} has connected to Discord!')

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return
        if message.content.lower() == 'hi':
            await message.channel.send('hello')

# Second bot using slash commands
class Bot2(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.interactions = DiscordInteractions(bot)
        self.register_commands()

    def register_commands(self):
        @self.interactions.command(name="hi", description="Responds with welcome")
        async def _hi(ctx: InteractionContext):
            await ctx.send("welcome")

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'{self.bot.user} has connected to Discord!')

def run_first_bot():
    bot1 = commands.Bot(command_prefix='!', intents=intents)
    bot1.add_cog(Bot1(bot1))
    bot1.run(TOKEN1)

def run_second_bot():
    bot2 = commands.Bot(command_prefix='!', intents=discord.Intents.default())
    bot2.add_cog(Bot2(bot2))
    bot2.run(TOKEN2)

# Run the bots in separate threads
thread1 = threading.Thread(target=run_first_bot)
thread2 = threading.Thread(target=run_second_bot)

thread1.start()
thread2.start()

thread1.join()
thread2.join()
