import discord
from discord.ext import commands
from discord_slash import SlashCommand, SlashContext
from discord_slash.utils.manage_commands import create_option
import requests
import os
from lxml import etree
import subprocess
from PIL import Image
from datetime import datetime
from collections import Counter

# Define paths
HULLS_FILE_PATH = './hulls.txt'
COMPONENTS_FILE_PATH = './components.txt'
TEMP_DIR = './'
BLEND_FILES_DIR = './'
DISCORD_TOKEN = 'DISCORD_TOKEN'
LOG_FILE_PATH = './command_log.txt'
SPECIFIC_USER_ID = '418309233193517056'  # this is my (sirpoopit) user id
WHITELIST_FILE_PATH = './whitelist.txt'
USE_WHITELIST = True

# Define intents
intents = discord.Intents.default()
intents.message_content = True

# Create a bot instance with intents
bot = commands.Bot(command_prefix='/', intents=intents)
slash = SlashCommand(bot, sync_commands=True)  # sync_commands=True to register commands on Discord

# Function to download the attached file
async def download_attachment(url, filename):
    response = requests.get(url)
    with open(filename, 'wb') as f:
        f.write(response.content)

# Function to handle the Blender operations in the command line
def process_blend_file(hull_type, component_names, key_object_names, output_path, ship_file_path):
    blend_path = os.path.join(BLEND_FILES_DIR, f"{hull_type}.blend")

    script_content = f"""
import bpy
import os
from lxml import etree

bpy.ops.wm.open_mainfile(filepath="{blend_path}")

def find_arrow_transform(key):
    obj = bpy.data.objects.get(key)
    if obj:
        return obj.location, obj.rotation_euler
    return None, None

ship_file_path = "{ship_file_path}"
tree = etree.parse(ship_file_path)
root = tree.getroot()

for hull_socket in root.findall('.//HullSocket'):
    key = hull_socket.find('Key').text
    component_name = hull_socket.find('ComponentName').text.replace('/', '/')
    component_blend_path = os.path.join("{BLEND_FILES_DIR}", f"{{component_name}}.blend")

    if not os.path.exists(component_blend_path):
        print(f"Component {{component_name}} not found at {{component_blend_path}}")
        continue

    with bpy.data.libraries.load(component_blend_path, link=False) as (data_from, data_to):
        data_to.objects = data_from.objects
        
    for obj in data_to.objects:
        if obj is not None:
            bpy.context.collection.objects.link(obj)
            location, rotation = find_arrow_transform(key)
            if location and rotation:
                obj.location = location
                obj.rotation_euler = rotation
                obj.rotation_euler.rotate_axis('X', 1.5708)
                obj.rotation_euler.rotate_axis('Y', 3.14159)

bpy.ops.export_mesh.stl(filepath="{output_path}")
"""

    script_path = os.path.join(TEMP_DIR, 'blender_script.py')
    with open(script_path, 'w') as script_file:
        script_file.write(script_content)

    blender_command = [
        'blender', '--background', '--factory-startup', '--python', script_path
    ]
    subprocess.run(blender_command, check=True)
    os.remove(script_path)

# Function to read ship data from the XML file
def read_ship_data(file_path):
    keys = []
    hull_type = None
    component_names = []

    tree = etree.parse(file_path)
    root = tree.getroot()

    hull_type = root.find('.//HullType').text
    for hull_socket in root.findall('.//HullSocket'):
        key = hull_socket.find('.//Key').text
        component_name = hull_socket.find('.//ComponentName').text
        keys.append(key)
        component_names.append(component_name)

    return keys, hull_type, component_names

# Function to resize image and reduce the file size
def resize_image(input_path, output_path, target_size=(256, 256), max_file_size=37000):
    with Image.open(input_path) as img:
        img = img.resize(target_size, Image.LANCZOS).convert("RGBA")
        img = img.quantize(colors=128)

        quality = 95
        while True:
            img.save(output_path, 'PNG', quality=quality, optimize=True)
            if os.path.getsize(output_path) < max_file_size or quality <= 10:
                break
            quality -= 5

# Function to log commands
def log_command(command, user):
    with open(LOG_FILE_PATH, 'a') as log_file:
        log_file.write(f'{datetime.now()} - {user}: {command}\n')

# Function to generate the balls leaderboard
def get_top_users():
    with open(LOG_FILE_PATH, 'r') as log_file:
        logs = log_file.readlines()

    users = [log.split('-')[3].split(':')[0].strip() for log in logs if 'balls' in log]
    user_counts = Counter(users)
    top_users = user_counts.most_common(3)

    return top_users

# Function to read the whitelist
def read_whitelist(file_path):
    with open(file_path, 'r') as f:
        return [line.strip() for line in f]

# Function to check if a user or server is whitelisted
def is_whitelisted(user_id, server_id):
    if not USE_WHITELIST:
        return True
    whitelist = read_whitelist(WHITELIST_FILE_PATH)
    return str(user_id) in whitelist or str(server_id) in whitelist

# Slash command to display the top users who used "balls"
@slash.slash(name="balls", description="Displays top users who used 'balls'")
async def balls(ctx: SlashContext):
    if not is_whitelisted(ctx.author.id, ctx.guild.id):
        await ctx.send("womp womp", hidden=True)
        log_command('not whitelisted', ctx.author)
        return

    top_users = get_top_users()
    if top_users:
        top_users_message = "# Top 3 ballers \n"
        for user, count in top_users:
            top_users_message += f"{user}: {count} times\n"
        await ctx.send(top_users_message)
    else:
        await ctx.send("No one has used the 'balls' command yet.")
    log_command('balls', ctx.author)

# Slash command to process .ship files and return .stl
@slash.slash(name="engrep", description="Processes .ship file and returns .stl",
             options=[
                 create_option(
                     name="file",
                     description="The .ship file to process",
                     option_type=3,  # 3 for string (file upload)
                     required=True
                 )
             ])
async def engrep(ctx: SlashContext, file: str):
    if not is_whitelisted(ctx.author.id, ctx.guild.id):
        await ctx.send("womp womp", hidden=True)
        log_command('not whitelisted', ctx.author)
        return

    if not file.lower().endswith('.ship'):
        await ctx.send('... Sir you wanted me to analyze something?', hidden=True)
        log_command('engrep - no .ship file', ctx.author)
        return

    attachment = ctx.args[0]
    file_path = os.path.join(TEMP_DIR, attachment.filename)
    await download_attachment(attachment.url, file_path)

    if file_path.endswith('.fleet'):
        await ctx.send('Sorry sir thats above my pay grade', hidden=True)
        log_command('engrep - .fleet file', ctx.author)
        os.remove(file_path)
        return
    elif file_path.endswith('.missile'):
        await ctx.send('Sorry sir thats not my area of expertise', hidden=True)
        log_command('engrep - .missile file', ctx.author)
        os.remove(file_path)
        return

    keys, hull_type, component_names = read_ship_data(file_path)

    with open(HULLS_FILE_PATH, 'r') as f:
        valid_hulls = [line.strip() for line in f]
    if hull_type not in valid_hulls:
        await ctx.send('Sorry sir I havent worked with that hull before', hidden=True)
        log_command('engrep - invalid hull type', ctx.author)
        os.remove(file_path)
        return

    with open(COMPONENTS_FILE_PATH, 'r') as f:
        valid_components = [line.strip() for line in f]
    component_names = [c for c in component_names if c in valid_components]

    output_path = os.path.join(TEMP_DIR, f'{hull_type}.stl')
    process_blend_file(hull_type, component_names, keys, output_path, file_path)

    with open(output_path, 'rb') as f:
        await ctx.send(file=discord.File(f, f'{hull_type}.stl'))

    os.remove(file_path)
    os.remove(output_path)
    log_command('engrep', ctx.author)

# Slash command to resize .png files
@slash.slash(name="resize", description="Resizes .png file",
             options=[
                 create_option(
                     name="file",
                     description="The .png file to resize",
                     option_type=3,  # 3 for string (file upload)
                     required=True
                 )
             ])
async def resize(ctx: SlashContext, file: str):
    if not is_whitelisted(ctx.author.id, ctx.guild.id):
        await ctx.send("womp womp", hidden=True)
        log_command('not whitelisted', ctx.author)
        return

    if not file.lower().endswith('.png'):
        await ctx.send('... Sir you wanted me to resize something?', hidden=True)
        log_command('resize - no .png file', ctx.author)
        return

    attachment = ctx.args[0]
    input_path = os.path.join(TEMP_DIR, attachment.filename)
    output_path = os.path.join(TEMP_DIR, f"badge_compatible_{attachment.filename}")
    await download_attachment(attachment.url, input_path)

    resize_image(input_path, output_path)

    with open(output_path, 'rb') as f:
        await ctx.send(file=discord.File(f, f'badge_compatible_{attachment.filename}'))

    os.remove(input_path)
    os.remove(output_path)
    log_command('resize', ctx.author)

# Slash command to send command log to specific user
@slash.slash(name="log", description="Sends command log to specific user")
async def log(ctx: SlashContext):
    if not is_whitelisted(ctx.author.id, ctx.guild.id):
        await ctx.send("womp womp", hidden=True)
        log_command('not whitelisted', ctx.author)
        return

    try:
        user = await bot.fetch_user(SPECIFIC_USER_ID)
        with open(LOG_FILE_PATH, 'rb') as log_file:
            await user.send(file=discord.File(log_file, 'command_log.txt'))
        log_command('log', ctx.author)
    except Exception as e:
        await ctx.send(f"Failed to send log file: {str(e)}", hidden=True)

# Event to signify the bot is ready
@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

# Run the bot
bot.run(DISCORD_TOKEN)
