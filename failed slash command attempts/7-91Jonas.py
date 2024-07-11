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

# Create a new Discord bot instance
bot = commands.Bot(command_prefix='!')
slash = SlashCommand(bot, sync_commands=True)  # sync_commands=True to register commands on Discord


# Function to download the attached file
async def download_attachment(url, filename):
    response = requests.get(url)
    with open(filename, 'wb') as f:
        f.write(response.content)


# Function to handle the Blender operations in the command line
def process_blend_file(hull_type, component_names, key_object_names, output_path, ship_file_path):
    # Path to the hull .blend file
    blend_path = os.path.join(BLEND_FILES_DIR, f"{hull_type}.blend")

    # Create a Blender script to be executed
    script_content = f"""
import bpy
import os
from lxml import etree

# Open the main hull .blend file
bpy.ops.wm.open_mainfile(filepath="{blend_path}")

# Function to find the location and rotation of the arrow object that correlates with the HullSockets key
def find_arrow_transform(key):
    obj = bpy.data.objects.get(key)
    if obj:
        return obj.location, obj.rotation_euler
    return None, None

# Load the .ship file and parse it
ship_file_path = "{ship_file_path}"
tree = etree.parse(ship_file_path)
root = tree.getroot()

# Iterate through HullSocket elements
for hull_socket in root.findall('.//HullSocket'):
    key = hull_socket.find('Key').text
    component_name = hull_socket.find('ComponentName').text.replace('/', '/')
    component_blend_path = os.path.join("{BLEND_FILES_DIR}", f"{{component_name}}.blend")

    # Check if component file exists
    if not os.path.exists(component_blend_path):
        print(f"Component {{component_name}} not found at {{component_blend_path}}")
        continue

    # Append the component .blend file
    with bpy.data.libraries.load(component_blend_path, link=False) as (data_from, data_to):
        data_to.objects = data_from.objects
        
    # Rotate the object
    for obj in data_to.objects:
        if obj is not None:
            bpy.context.collection.objects.link(obj)
            location, rotation = find_arrow_transform(key)
            if location and rotation:
                obj.location = location  # Set the object's location to the arrow location
                obj.rotation_euler = rotation  # Set the object's rotation to the arrow rotation

                # Rotate the component 90 degrees around the X axis and 180 degrees around the Y axis
                obj.rotation_euler.rotate_axis('X', 1.5708)  # 90 degrees
                obj.rotation_euler.rotate_axis('Y', 3.14159)  # 180 degrees

# Export the result as .stl
bpy.ops.export_mesh.stl(filepath="{output_path}")
"""

    # Write the script to a temporary file
    script_path = os.path.join(TEMP_DIR, 'blender_script.py')
    with open(script_path, 'w') as script_file:
        script_file.write(script_content)

    # Run the Blender command
    blender_command = [
        'blender', '--background', '--factory-startup', '--python', script_path
    ]
    subprocess.run(blender_command, check=True)

    # Clean up the temporary script file
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

        # Reduce file size until it is smaller than the target size
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


# Slash command to return the leaderboard for the top 3 people that have said "balls"
@slash.slash(name="balls", description="Returns the top 3 ballers")
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


# Slash command to input a .ship file and return a .stl file
@slash.slash(name="engrep", description="Inputs a .ship file and returns a .stl file",
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

    file_path = os.path.join(TEMP_DIR, file)

    if file_path.endswith('.fleet'):
        await ctx.send('Sorry sir thats above my pay grade', hidden=True)
        log_command('engrep - .fleet file', ctx.author)
        return
    elif file_path.endswith('.missile'):
        await ctx.send('Sorry sir thats not my area of expertise', hidden=True)
        log_command('engrep - .missile file', ctx.author)
        return

    # Read ship data from the file
    keys, hull_type, component_names = read_ship_data(file_path)

    # Check hull type
    with open(HULLS_FILE_PATH, 'r') as f:
        valid_hulls = [line.strip() for line in f]
    if hull_type not in valid_hulls:
        await ctx.send('Sorry sir I havent worked with that hull before', hidden=True)
        log_command('engrep - invalid hull type', ctx.author)
        return

    # Check component names
    with open(COMPONENTS_FILE_PATH, 'r') as f:
        valid_components = [line.strip() for line in f]
    component_names = [c for c in component_names if c in valid_components]

    # Process the hull type
    output_path = os.path.join(TEMP_DIR, f'{hull_type}.stl')
    process_blend_file(hull_type, component_names, keys, output_path, file_path)

    # Upload the resulting STL file
    await ctx.send(file=discord.File(output_path, f'{hull_type}.stl'))

    # Clean up temporary files
    os.remove(file_path)
    os.remove(output_path)

    log_command('engrep', ctx.author)


# Slash command to input a .png and return that .png resized and degraded
@slash.slash(name="resize", description="Inputs a .png and returns it resized and degraded",
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

    input_path = os.path.join(TEMP_DIR, file)

    if not input_path.lower().endswith('.png'):
        await ctx.send('Sorry sir I havent worked with that format before', hidden=True)
        log_command('resize - not a PNG', ctx.author)
        return

    output_path = os.path.join(TEMP_DIR, f"badge_compatible_{file}")

    # Resize the image
    resize_image(input_path, output_path)

    # Upload the resized image
    await ctx.send(file=discord.File(output_path, f'badge_compatible_{file}'))

    # Clean up temporary files
    os.remove(input_path)
    os.remove(output_path)

    log_command('resize', ctx.author)


# Slash command to send the command log
@slash.slash(name="log", description="Sends the command log")
async def log(ctx: SlashContext):
    if ctx.author.id != int(SPECIFIC_USER_ID):
        await ctx.send("You don't have permission to use this command.", hidden=True)
        return

    try:
        user = await bot.fetch_user(SPECIFIC_USER_ID)
        with open(LOG_FILE_PATH, 'rb') as log_file:
            await user.send(file=discord.File(log_file, 'command_log.txt'))
        await ctx.send("Log file sent.", hidden=True)
        log_command('log', ctx.author)
    except Exception as e:
        await ctx.send(f"Failed to send log file: {str(e)}", hidden=True)


# Event to signify the bot is ready
@bot.event
async def on_ready():
    print(f'{bot.user} reporting for duty')


# Run the bot
bot.run(DISCORD_TOKEN)
