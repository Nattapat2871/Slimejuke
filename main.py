import os
import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
import time

from alive import server_on

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='*', intents=intents)

# Global variables
queue = []
start_times = {}

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': True,  # Allow errors to be ignored
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.thumbnail = data.get('thumbnail')
        self.duration = data.get('duration')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
            if 'entries' in data:
                data = data['entries'][0]
            filename = data['url'] if stream else ytdl.prepare_filename(data)
            return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)
        except youtube_dl.DownloadError as e:
            raise ValueError(f"Error downloading video: {e}")

@bot.event
async def on_ready():
    print(f'เข้าสู่ระบบเป็น {bot.user}')

async def play_next(ctx):
    if len(queue) > 0:
        url = queue.pop(0)
        try:
            player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
            start_times[ctx.guild.id] = time.time()
            ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop).result())
            await show_music_info(ctx)
        except ValueError as e:
            await ctx.send(f"เกิดข้อผิดพลาดในการเล่นเพลง: {e}")
            await play_next(ctx)
    else:
        await ctx.send("ไม่มีเพลงในคิว.")

async def show_music_info(ctx):
    if ctx.voice_client.is_playing():
        current_player = ctx.voice_client.source
        current_title = current_player.title
        current_duration = current_player.duration
        current_thumbnail = current_player.thumbnail

        start_time = start_times.get(ctx.guild.id, time.time())
        while ctx.voice_client.is_playing():
            elapsed_time = time.time() - start_time
            elapsed_time_str = f"{int(elapsed_time // 60)}:{int(elapsed_time % 60):02d}"
            duration_str = f"{current_duration // 60}:{current_duration % 60:02d}"
            
            embed = discord.Embed(title="ข้อมูลเพลง", color=0x00ff00)
            embed.add_field(name="เพลงปัจจุบัน", value=current_title, inline=False)
            embed.add_field(name="ระยะเวลา", value=f"{elapsed_time_str} / {duration_str}", inline=False)
            embed.add_field(name="คิวเพลง", value="\n".join(queue) if queue else "คิวเพลงว่าง", inline=False)

            if current_thumbnail:
                embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1140325634200064050/1275701148816244786/rimuru-tempest-playful-finger-dance-ybt447yf6vjmub3i.gif?ex=66c6d8c7&is=66c58747&hm=9e5135b4c1ed17dfc8bdc33ca5685621f5f97bf2768abab5b73e07f112ebda91&")

            embed.set_image(url=current_thumbnail)
            embed.set_footer(text="พัฒนาโดย Nattapat2871")

            if hasattr(ctx, 'music_info_message') and ctx.music_info_message:
                await ctx.music_info_message.edit(embed=embed)
            else:
                ctx.music_info_message = await ctx.send(embed=embed)
                
            await asyncio.sleep(0.5)
    else:
        await ctx.send("ไม่มีเพลงเล่นอยู่ตอนนี้")

@bot.command(name='play', aliases=['p'], help='เล่นเพลงจาก YouTube')
async def play(ctx, url):
    if not ctx.author.voice:
        await ctx.send("คุณยังไม่ได้เชื่อมต่อกับช่องเสียง.")
        return

    voice_channel = ctx.author.voice.channel

    if ctx.voice_client is None:
        await voice_channel.connect()

    async with ctx.typing():
        try:
            player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
            queue.append(url)
            start_times[ctx.guild.id] = time.time()
            if not ctx.voice_client.is_playing():
                await play_next(ctx)
            await show_music_info(ctx)
        except ValueError as e:
            await ctx.send(f"เกิดข้อผิดพลาดในการเล่นเพลง: {e}")

@bot.command(name='pause', help='หยุดเพลงชั่วคราว')
async def pause(ctx):
    if ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("เพลงถูกหยุดชั่วคราว.")
    else:
        await ctx.send("ไม่มีเพลงที่กำลังเล่นอยู่ตอนนี้.")

@bot.command(name='resume', help='เล่นเพลงที่หยุดชั่วคราว')
async def resume(ctx):
    if ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("เพลงถูกเล่นต่อ.")
    else:
        await ctx.send("ไม่มีเพลงที่หยุดชั่วคราวอยู่ตอนนี้.")

@bot.command(name='stop', help='หยุดเพลง')
async def stop(ctx):
    ctx.voice_client.stop()
    await ctx.send("เพลงถูกหยุด.")

@bot.command(name='leave', help='ให้บอทออกจากช่องเสียง')
async def leave(ctx):
    if ctx.voice_client is not None:
        await ctx.voice_client.disconnect()
        await ctx.send("ออกจากช่องเสียงแล้ว.")
    else:
        await ctx.send("บอทไม่อยู่ในช่องเสียง.")

@bot1.event
async def on_ready():
    print(f'Bot 1 Logged in as {bot1.user.name}')
    streaming_activity = discord.Streaming(
        name="ª ᴊᴜʀᴀ ᴛᴇᴍᴘᴇsᴛ sʜᴏᴘ™",
        url="https://www.twitch.tv/nattapat2871_"
    )
    await bot1.change_presence(activity=streaming_activity)

server_on()

bot.run(os.getenv('TOKEN'))
