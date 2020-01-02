import discord
from discord.ext import commands

import asyncio
import itertools
import sys
import traceback
from async_timeout import timeout
from functools import partial
#from youtube_dl import YoutubeDL
import json
import glob
import random

class MusicPlayer:
    __slots__ = ('bot', '_guild', '_channel', '_cog', 'queue', 'next', 'current', 'np', 'volume', 'loop')

    def __init__(self, ctx):
        self.bot = ctx.bot
        self._guild = ctx.guild
        self._channel = ctx.channel
        self._cog = ctx.cog

        self.queue = asyncio.Queue()
        self.next = asyncio.Event()

        self.np = None
        self.volume = .5
        self.current = None
        self.loop = asyncio.Event()

        ctx.bot.loop.create_task(self.player_loop())

    async def player_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            self.next.clear()
            source,music = await self.queue.get()
            #source.volume = self.volume
            self.current = source

            self._guild.voice_client.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set))
            self.np = await self._channel.send(f'**Now Playing:** `{music}`')

            await self.next.wait()

            self.current = None

    def destroy(self, guild):
        return self.bot.loop.create_task(self._cog.cleanup(guild))


class Music(commands.Cog):
    __slots__ = ('bot', 'players')

    def __init__(self, bot):
        self.bot = bot
        self.players = {}

    async def cleanup(self, guild):
        try:
            await guild.voice_client.disconnect()
        except AttributeError:
            pass

        try:
            del self.players[guild.id]
        except KeyError:
            pass

    async def __local_check(self, ctx):
        if not ctx.guild:
            raise commands.NoPrivateMessage
        return True

    async def __error(self, ctx, error):
        if isinstance(error, commands.NoPrivateMessage):
            try:
                return await ctx.send('This command can not be used in Private Messages.')
            except discord.HTTPException:
                pass
        elif isinstance(error, InvalidVoiceChannel):
            await ctx.send('Error connecting to Voice Channel. '
                           'Please make sure you are in a valid channel or provide me with one')

        print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    def get_player(self, ctx):
        try:
            player = self.players[ctx.guild.id]
        except KeyError:
            player = MusicPlayer(ctx)
            self.players[ctx.guild.id] = player

        return player

    @commands.command(name='connect', aliases=['join'])
    async def connect_(self, ctx, *, channel: discord.VoiceChannel = None):
        if not channel:
            try:
                channel = ctx.author.voice.channel
            except AttributeError:
                raise InvalidVoiceChannel('No channel to join. Please either specify a valid channel or join one.')

        vc = ctx.voice_client

        if vc:
            if vc.channel.id == channel.id:
                return
            try:
                await vc.move_to(channel)
            except asyncio.TimeoutError:
                raise VoiceConnectionError(f'Moving to channel: <{channel}> timed out.')
        else:
            try:
                await channel.connect()
            except asyncio.TimeoutError:
                raise VoiceConnectionError(f'Connecting to channel: <{channel}> timed out.')

        await ctx.send(f'Connected to: **{channel}**')


    @commands.command(name='play_all')
    async def all_(self, ctx):
#        await ctx.trigger_typing()

        vc = ctx.voice_client

        if not vc:
            await ctx.invoke(self.connect_)

        player = self.get_player(ctx)
        music_list = glob.glob("../priconne_song/*")

        for music in music_list:
            source = discord.FFmpegPCMAudio(music)
            txt = music.replace("../priconne_song/","")
            await player.queue.put([source,txt])

    @commands.command()
    async def loop(self, ctx):
        if not self.get_player(ctx).loop.is_set():
            self.get_player(ctx).loop.set()
            await ctx.send("The queue is being looped.")
        else:
            self.get_player(ctx).loop.clear()
            await ctx.send("The queue isn't being looped.")

    @commands.command(name='pause')
    async def pause_(self, ctx):
        vc = ctx.voice_client

        if not vc or not vc.is_playing():
            return await ctx.send('I am not currently playing anything!')
        elif vc.is_paused():
            return

        vc.pause()
        await ctx.send(f'**`{ctx.author}`**: Paused the song!')

    @commands.command(name='resume')
    async def resume_(self, ctx):
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently playing anything!')
        elif not vc.is_paused():
            return

        vc.resume()
        await ctx.send(f'**`{ctx.author}`**: Resumed the song!')

    @commands.command(name='skip')
    async def skip_(self, ctx):
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently playing anything!')

        if vc.is_paused():
            pass
        elif not vc.is_playing():
            return

        vc.stop()
        await ctx.send(f'**`{ctx.author}`**: Skipped the song!')

    @commands.command(name='queue', aliases=['q', 'playlist'])
    async def queue_info(self, ctx):
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently connected to voice!')

        player = self.get_player(ctx)
        if player.queue.empty():
            return await ctx.send('There are currently no more queued songs.')

        # Grab up to 5 entries from the queue...
        upcoming = list(itertools.islice(player.queue._queue, 0, 5))

        fmt = '\n'.join(f'**`{_["title"]}`**' for _ in upcoming)
        embed = discord.Embed(title=f'Upcoming - Next {len(upcoming)}', description=fmt)

        await ctx.send(embed=embed)

    @commands.command(name='volume', aliases=['vol'])
    async def change_volume(self, ctx, *, vol: float = None):
        vc = ctx.voice_client
        player = self.get_player(ctx)
        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently connected to voice!')
        if vol is None:
            return await ctx.send('The current volume is ' + str(player.volume))
        if not 0 <= vol <= 100:
            return await ctx.send('Please enter a value between 0 and 100.')

        if vc.source:
            vc.source.volume = vol / 100

        player.volume = vol / 100
        await ctx.send(f'**`{ctx.author}`**: Set the volume to **{vol}%**')

    @commands.command(name='stop')
    async def stop_(self, ctx):
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently playing anything!')

        await self.cleanup(ctx.guild)
    
    @commands.command(name="play")
    async def play(self,ctx,number=1):

        vc = ctx.voice_client
        if not vc:
            await ctx.invoke(self.connect_)


        player = self.get_player(ctx)
        music_list = glob.glob("../priconne_song/*")

        music = music_list[number]
        source = discord.FFmpegPCMAudio(music)
        txt = music.replace("../priconne_song/","")
        await player.queue.put([source,txt])
    
    @commands.command()
    async def random_play(self,ctx):

        vc = ctx.voice_client

        if not vc:
            await ctx.invoke(self.connect_)

        player = self.get_player(ctx)
        music_list = glob.glob("../priconne_song/*")
        random.shuffle(music_list)

        for music in music_list:
            source = discord.FFmpegPCMAudio(music)
            txt = music.replace("../priconne_song/","")
            await player.queue.put([source,txt])
        

bot = commands.Bot(command_prefix=commands.when_mentioned_or("!"),
                   description='Relatively simple music bot example')

@bot.event
async def on_ready():
    print('Logged in as {0} ({0.id})'.format(bot.user))
    print('------')

with open("config.json","r") as f:
    TOKEN = json.load(f)["DISCORD_MUSIC_TOKEN"]

bot.add_cog(Music(bot))
bot.run(TOKEN)
