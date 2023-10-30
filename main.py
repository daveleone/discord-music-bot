import nextcord, os, asyncio, yt_dlp, glob
from nextcord.ext import commands
from nextcord import FFmpegPCMAudio

intents = nextcord.Intents().all()
client = nextcord.Client(intents=intents)
bot = commands.Bot(command_prefix='.',intents=intents)

yt_dlp.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(nextcord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.filename = ytdl.prepare_filename(data)
        self.uploader = data.get('uploader')  # Get the uploader name
        self.extra_info = data.get('extra_info')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(FFmpegPCMAudio(filename), data=data)

class Player(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.current_song = None
        self.queue = []
        self.ctx = None
        self.queue_message = None

    def delete_song(self, filename):
        if filename is not None:
            os.remove(filename)
            self.current_song = None

    def remove_song(self, url):
        data = ytdl.extract_info(url, download=False)
        filename = ytdl.prepare_filename(data)
        if filename is not None and os.path.isfile(filename):
            os.remove(filename)

    def play_next_song(self, e):
        self.bot.loop.create_task(self.play_next_song_coroutine(e))
    
    async def play_next_song_coroutine(self, e):
        voice_channel = e
        if len(self.queue) > 0:
            url = self.queue.pop(0)
            player = await YTDLSource.from_url(url, loop=self.bot.loop)
            voice_channel.play(player, after=lambda e: self.play_next_song(e))
            embed = nextcord.Embed(title="Now playing", description=f"[{player.title}]({url})", color=nextcord.Color.green())
            embed.add_field(name="Added by", value=self.ctx.author.mention, inline=False)
            await self.ctx.send(embed=embed)
            self.current_song = player.filename
        else:
            self.current_song = None
            if voice_channel is not None:  # Check if the bot is connected to a voice channel
                voice_channel.stop()  # Stop the audio playback
            self.delete_song(self.current_song)  # Delete the current song
            # Delete all .webm files
            for file in glob.glob("*.webm"):
                os.remove(file)
    
    @commands.command(aliases=['p'])
    async def play(self, ctx, *, url):
        print(url)
        self.ctx = ctx
        server = ctx.guild
        voice_channel = server.voice_client

        if voice_channel is None:
            voice_channel = await ctx.author.voice.channel.connect()

        async with ctx.typing():
            player = await YTDLSource.from_url(url, loop=self.bot.loop)

            # Check if the channel name is 'Matteo Leonetti'
            if player.uploader.lower() == 'matteo leonetti':
                embed = nextcord.Embed(title="No More Matteo Leonetti", description='Sorry but my Developer instructed me to not allow anyone to play any songs from this channel', color=nextcord.Color.green())
                await ctx.send(embed=embed)
            else:
                if voice_channel.is_playing():
                    # If the bot is already playing a song, add the new song to the queue
                    self.queue.append(url)
                    embed = nextcord.Embed(title="Queue", description=f"[{player.title}]({url})", color=nextcord.Color.green())
                    embed.add_field(name="Added by", value=ctx.author.mention, inline=False)
                    await ctx.send(embed=embed)
                else:
                    # If the bot is not playing a song, play the new song
                    voice_channel.play(player, after=lambda e: self.play_next_song(voice_channel))
                    embed = nextcord.Embed(title="Now Playing", description=f"[{player.title}]({url})", color=nextcord.Color.green())
                    embed.add_field(name="Added by", value=ctx.author.mention, inline=False)
                    await ctx.send(embed=embed)

                self.current_song = player.filename

            await ctx.message.edit(suppress=True)

    @commands.command(aliases=['s'])
    async def skip(self, ctx):
        voice_channel = ctx.voice_client
        if voice_channel is None:
            embed = nextcord.Embed(title="Skip", description = "The bot is not connected to a voice channel.", color=nextcord.Color.green())
            await ctx.send(embed=embed)
            return
        if voice_channel.is_playing():
            voice_channel.stop()  # Stop the audio playback
            embed = nextcord.Embed(title="Skip", color=nextcord.Color.green())
            embed.add_field(name="Skipped by", value=ctx.author.mention, inline=False)
            await ctx.send(embed=embed)
            self.delete_song(self.current_song)  # Delete the current song
            self.current_song = None
        else:
            embed = nextcord.Embed(title="Skip", description = "No song is playing.", color=nextcord.Color.green())
            await ctx.send(embed=embed)

    @commands.command(pass_context=True)
    async def pause(self, ctx):
        voice_channel = ctx.voice_client
        if voice_channel is None:
            embed = nextcord.Embed(title="Pause", description = "The bot is not connected to a voice channel.", color=nextcord.Color.green())
            await ctx.send(embed=embed)
            return
        if voice_channel.is_playing():
            voice_channel.pause()
        else:
            await ctx.send("No song is currently playing.")

    @commands.command(pass_context=True, alises = ['p'])
    async def resume(self, ctx):
        voice_channel = ctx.voice_client
        if voice_channel is None:
            embed = nextcord.Embed(title="Resume", description = "The bot is not connected to a voice channel.", color=nextcord.Color.green())
            await ctx.send(embed=embed)
            return
        if voice_channel.is_paused():
            voice_channel.resume()
        else:
            await ctx.send("No song is currently paused.")

    @commands.command(pass_context=True, aliases = ['q'])
    async def queue(self, ctx):
        embed = nextcord.Embed(title="Songs in Queue", color=nextcord.Color.green())
        if len(self.queue) > 0:
            for i, url in enumerate(self.queue):
                embed.add_field(name=f"{i+1}.", value=f"[{url}]({url})", inline=False)
        else:
            embed.description = "The queue is empty."
        await ctx.send(embed=embed)

    @commands.command(pass_context=True)
    async def remove(self, ctx, index: int):
        if 0 < index <= len(self.queue):
            removed_song = self.queue.pop(index - 1)
            self.remove_song(removed_song)  # Remove the song file
            embed = nextcord.Embed(title="Resume", description = f"Removed {removed_song} from the queue.", color=nextcord.Color.green())
            await ctx.send(embed=embed)
        else:
            embed = nextcord.Embed(title="Resume", description = "Invalid index.", color=nextcord.Color.green())
            await ctx.send(embed=embed)


async def setup():
    bot.add_cog(Player(bot))

@bot.event
async def on_ready():
    await setup()
    
@bot.slash_command(name = 'badge', guild_ids=[859497732673896458])
async def claim_badge(interaction: nextcord.Interaction):
    """
    Use this command to claim the active developer badge
    """
    # Code to claim the badge goes here
    await interaction.response.send_message("Badge claimed!")

if __name__ == "__main__":
    bot.run('')