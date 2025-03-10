# Test under process

import discord
from discord.ext import commands, tasks
import time
# import config
import os
from datetime import datetime, timedelta
import json



intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="-", intents=intents, help_command=None)
user_times = {}


DATA_FILE = "study_data.json"

def save_data():
    with open(DATA_FILE, "w") as file:
        json.dump(user_times,file)

def load_data():
    global user_times
    try:
        with open(DATA_FILE, "r") as file:
            user_times = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        user_times = {}

@tasks.loop(minutes=5)
async def auto_save():
    save_data()
    print("Study data saved.")

last_reset = None  # Global variable to track last reset time

@tasks.loop(hours=1)
async def reset_timer():
    global last_reset, user_times
    now = datetime.now()
    
    if now.hour == 5 and now.minute == 0:
        if last_reset != now.date():  # Check if reset has already happened today
            user_times = {}  # Reset only once per day
            last_reset = now.date()  # Store reset date
            print("Resetting study timers at 5:00 AM")


@bot.event
async def on_ready():
    load_data()     # Loads saved data from the start
    print(f"Logged in as {bot.user}")
    reset_timer.start()
    auto_save.start()    # Start periodic using

@bot.event
async def on_disconnect():
    save_data()


@bot.command()
async def ping(ctx):
    embed = discord.Embed(title="🏓 Pong!", description=f"Latency: {round(bot.latency * 1000)}ms", color=discord.Color.green())
    await ctx.send(embed=embed)


@bot.command()
async def help(ctx):
    embed = discord.Embed(title="📖 StudyMate Bot Commands", description="Boost your productivity with these commands!", color=discord.Color.purple())
    
    embed.add_field(name="🟢 **Study Commands**\n", value="📚 `-start study` - Begin a study session\n☕ `-start break` - Take a break and recharge", inline=False)
    
    embed.add_field(name="📊 **Statistics Commands\n**", value="📅 `-daily [@user]` - View today's study performance\n📅 `-weekly [@user]` - Check weekly study stats\n📅 `-monthly [@user]` - See monthly study stats", inline=False)
    
    embed.add_field(name="🏆 **Leaderboard Commands\n**", value="🥇 `-lb daily` - Daily top students\n🥈 `-lb weekly` - Weekly leaderboard\n🥉 `-lb monthly` - Monthly ranking", inline=False)
    
    embed.add_field(name="⚙️ **Utility Commands\n**", value="🏓 `-ping` - Check bot latency\n", inline=False)
    
    embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/2995/2995427.png")  
    embed.set_footer(text="💡 Tip: Use -daily, -weekly, or -monthly with @user to check their stats!")

    await ctx.send(embed=embed)


@bot.command()
async def start(ctx, mode: str = None):
    user_id = ctx.author.id
    now = datetime.now()
    five_am_today = now.replace(hour=5, minute=0, second=0, microsecond=0).timestamp()
    
    if mode is None:
        embed = discord.Embed(title="⚠️ Invalid Usage", description="Use `-start study` or `-start break`.", color=discord.Color.red())
        await ctx.send(embed=embed)
        return
    
    if user_id not in user_times:
        user_times[user_id] = {"sessions": [], "is_studying": False, "start_time": None}
    
    if mode.lower() == "study":
        if user_times[user_id]["is_studying"]:
            embed = discord.Embed(title="⚠️ Already Studying", description="You're already in a study session! Use `-start break` when needed.", color=discord.Color.red())
        else:
            user_times[user_id]["start_time"] = time.time()
            user_times[user_id]["is_studying"] = True
            embed = discord.Embed(title="✅ Study Started", description="Stay focused! 📚", color=discord.Color.green())
    
    elif mode.lower() == "break":
        if user_times[user_id]["start_time"] is None:
            embed = discord.Embed(title="⚠️ Error", description="You haven't started studying yet! (Study data resets daily at 5:00 AM ⏳)", color=discord.Color.red())
        elif not user_times[user_id]["is_studying"]:
            embed = discord.Embed(title="⚠️ Already on Break", description="You're already taking a break! Use `-start study` to resume.", color=discord.Color.red())
        else:
            start_time = user_times[user_id]["start_time"]
            end_time = time.time()
            
            # Handling 5:00 AM reset issue
            if start_time < five_am_today < end_time:
                user_times[user_id]["sessions"].append((start_time, five_am_today - 1))  # Assign past time to previous day
                user_times[user_id]["sessions"].append((five_am_today, end_time))  # Assign new time to today
            else:
                user_times[user_id]["sessions"].append((start_time, end_time))
            
            user_times[user_id]["is_studying"] = False
            user_times[user_id]["start_time"] = None
            embed = discord.Embed(title="☕ Break Started", description="Take a short break and recharge!", color=discord.Color.orange())
    
    else:
        embed = discord.Embed(title="⚠️ Invalid Mode", description="Use `-start study` or `-start break`.", color=discord.Color.red())
    
    await ctx.send(embed=embed)


@bot.command()
async def daily(ctx, member: discord.Member = None):
    user_id = member.id if member else ctx.author.id
    await send_study_stats(ctx, user_id, datetime.now().replace(hour=5, minute=0, second=0, microsecond=0), "📅 Today's Study Performance")


@bot.command()
async def weekly(ctx, member: discord.Member = None):
    user_id = member.id if member else ctx.author.id
    start_of_week = datetime.now() - timedelta(days=datetime.now().weekday())
    start_of_week = start_of_week.replace(hour=5, minute=0, second=0, microsecond=0)
    await send_study_stats(ctx, user_id, start_of_week, "📅 Weekly Study Performance")


@bot.command()
async def monthly(ctx, member: discord.Member = None):
    user_id = member.id if member else ctx.author.id
    start_of_month = datetime.now().replace(day=1, hour=5, minute=0, second=0, microsecond=0)
    await send_study_stats(ctx, user_id, start_of_month, "📅 Monthly Study Performance")


async def send_study_stats(ctx, user_id, start_period, title):
    if user_id not in user_times or not user_times[user_id]["sessions"]:
        embed = discord.Embed(title=title, description="No study sessions recorded.", color=discord.Color.red())
    else:
        sessions_filtered = [s for s in user_times[user_id]["sessions"] if s[0] >= start_period.timestamp()]
        total_study_time = sum(end - start for start, end in sessions_filtered)
        study_sessions = "\n".join([f"🕒 {datetime.fromtimestamp(start).strftime('%H:%M')} - {datetime.fromtimestamp(end).strftime('%H:%M')}" for start, end in sessions_filtered])
        embed = discord.Embed(title=title, color=discord.Color.green())
        embed.add_field(name="📚 Study Sessions", value=study_sessions if study_sessions else "No study sessions recorded", inline=False)
        embed.add_field(name="⏳ Total Study Time", value=f"{round(total_study_time / 3600, 2)} hours", inline=False)
    await ctx.send(embed=embed)


@bot.command()
async def lb(ctx, period: str = None):
    if period is None:
        embed = discord.Embed(
            title="⚠️ Missing Argument",
            description="Please specify a period!\nUse: `-lb daily`, `-lb weekly`, or `-lb monthly`.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
    
    period_map = {
        "daily": datetime.now().replace(hour=5, minute=0, second=0, microsecond=0),
        "weekly": (datetime.now() - timedelta(days=datetime.now().weekday())).replace(hour=5, minute=0, second=0, microsecond=0),
        "monthly": datetime.now().replace(day=1, hour=5, minute=0, second=0, microsecond=0)
    }
    
    period = period.lower()
    
    if period not in period_map:
        embed = discord.Embed(
            title="⚠️ Invalid Period",
            description="Invalid period provided!\nUse: `-lb daily`, `-lb weekly`, or `-lb monthly`.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
    
    leaderboard = {}
    start_period = period_map[period]
    
    for user_id, data in user_times.items():
        sessions_filtered = [s for s in data["sessions"] if s[0] >= start_period.timestamp()]
        total_study_time = sum(end - start for start, end in sessions_filtered)
        if total_study_time > 0:
            leaderboard[user_id] = total_study_time
    
    sorted_leaderboard = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)
    
    embed = discord.Embed(title=f"🏆 {period.capitalize()} Study Leaderboard", color=discord.Color.blue())
    if not sorted_leaderboard:
        embed.description = "No study sessions recorded."
    else:
        for rank, (user_id, study_time) in enumerate(sorted_leaderboard, start=1):
            member = ctx.guild.get_member(user_id)
            username = member.display_name if member else f"User {user_id}"
            embed.add_field(name=f"#{rank} {username}", value=f"⏳ {round(study_time / 3600, 2)} hours", inline=False)
    
    await ctx.send(embed=embed)

TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
# bot.run(config.BOT_TOKEN)
