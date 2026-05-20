import discord
from discord.ext import commands
from gtts import gTTS
import asyncio
import os
from datetime import datetime

TOKEN = os.getenv("KI_TOKEN")

# IDs
BEWERBUNG_CATEGORY_ID = 1504190916737368328
PANEL_CHANNEL_ID = 1504203869130064035
WARTERAUM_VOICE_CHANNEL_ID = 1506271397591126078
BUERO_VOICE_CHANNEL_ID = 1506271506454544548

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

processing_tickets = set()


def kanal(guild, name):
    return discord.utils.get(guild.text_channels, name=name)


async def safe_send(channel, content=None, embed=None):
    try:
        if channel:
            await channel.send(content=content, embed=embed)
    except Exception as e:
        print(f"SEND FEHLER: {e}")


async def bot_speak(guild, text):
    try:
        voice = guild.get_channel(BUERO_VOICE_CHANNEL_ID)

        if not voice:
            print("Büro Voice nicht gefunden.")
            return

        if guild.voice_client:
            vc = guild.voice_client
            if vc.channel != voice:
                await vc.move_to(voice)
                await asyncio.sleep(1)
        else:
            vc = await asyncio.wait_for(voice.connect(), timeout=20)
            await asyncio.sleep(1)

        tts = gTTS(text=text, lang="de")
        tts.save("tts.mp3")

        if vc.is_playing():
            vc.stop()

        audio = discord.FFmpegPCMAudio("tts.mp3", executable="ffmpeg")
        vc.play(audio)

    except Exception as e:
        print(f"VOICE FEHLER: {e}")


async def move_to_buero(member):
    try:
        if not member.voice:
            return False

        buero = member.guild.get_channel(BUERO_VOICE_CHANNEL_ID)
        if not buero:
            return False

        await member.move_to(buero)
        return True

    except Exception as e:
        print(f"MOVE FEHLER: {e}")
        return False


def bewerbung_check(text):
    punkte = 100
    analyse = []
    lower = text.lower()

    fehlend = []
    for p in ["1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9."]:
        if p not in lower:
            fehlend.append(p)

    if fehlend:
        punkte -= len(fehlend) * 10
        analyse.append(f"❌ Fehlende Punkte: {', '.join(fehlend)}")

    if len(text) < 300:
        punkte -= 20
        analyse.append("❌ Bewerbung ist zu kurz.")

    gute_woerter = [
        "team", "respekt", "disziplin", "aktiv",
        "bundeswehr", "einsatz", "lernen",
        "erfahrung", "helfen", "kamerad"
    ]

    gefunden = sum(1 for wort in gute_woerter if wort in lower)

    if gefunden >= 6:
        punkte += 15
        analyse.append("✅ Sehr starke Motivation erkannt.")
    elif gefunden >= 4:
        punkte += 5
        analyse.append("✅ Gute Motivation erkannt.")
    elif gefunden >= 2:
        analyse.append("🟡 Motivation teilweise vorhanden.")
    else:
        punkte -= 20
        analyse.append("❌ Zu wenig Motivation.")

    schlechte_woerter = [
        "hurensohn", "niga", "nigger", "spast",
        "opfer", "kacke", "hs", "troll"
    ]

    if any(wort in lower for wort in schlechte_woerter):
        punkte -= 90
        analyse.append("❌ Beleidigungen/Troll-Inhalt erkannt.")

    if "ja" in lower:
        analyse.append("✅ Gesprächsbereit.")
    else:
        punkte -= 10
        analyse.append("🟡 Gesprächsbereitschaft unklar.")

    punkte = max(0, min(100, punkte))

    if fehlend:
        entscheidung = "UNVOLLSTÄNDIG"
    elif punkte >= 75:
        entscheidung = "ANGENOMMEN"
    else:
        entscheidung = "ABGELEHNT"

    return punkte, analyse, entscheidung, fehlend


class BewerbungSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Bundeswehr",
                description="Bewerbung starten",
                emoji="🪖"
            )
        ]

        super().__init__(
            placeholder="Bundeswehr Bewerbung auswählen",
            options=options,
            custom_id="bundeswehr_bewerbung_select"
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        category = guild.get_channel(BEWERBUNG_CATEGORY_ID)

        if not isinstance(category, discord.CategoryChannel):
            return await interaction.response.send_message(
                "❌ Bewerbungs-Kategorie nicht gefunden.",
                ephemeral=True
            )

        name = interaction.user.name.lower().replace(" ", "-")
        channel_name = f"bewerbung-{name}"

        existing = discord.utils.get(guild.text_channels, name=channel_name)

        if existing:
            return await interaction.response.send_message(
                f"⚠️ Du hast bereits ein Bewerbungsticket: {existing.mention}",
                ephemeral=True
            )

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True
            )
        }

        ticket = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites
        )

        embed = discord.Embed(
            title="🪖 Bundeswehr Bewerbung",
            description=(
                f"Willkommen {interaction.user.mention}!\n\n"
                "**Bitte beantworte alles in EINER Nachricht:**\n\n"
                "1. Wie alt sind sie?\n"
                "2. Wie heißen sie?\n"
                "3. Wie lange spielen sie schon Notruf Hamburg RP?\n"
                "4. Wie gut sind sie im Schießen?\n"
                "5. Warum wollen sie zur Bundeswehr?\n"
                "6. Was bringen sie mit?\n"
                "7. Warum sollen wir sie nehmen?\n"
                "8. Welche Kategorie wollen sie?\n"
                "9. Sind sie bereit für ein Gespräch? Ja/Nein\n\n"
                "⏳ Nach deiner Nachricht prüft der Bot automatisch nach 60 Sekunden.\n"
                "🔊 Wenn du im Warteraum bist, wirst du ins Büro verschoben."
            ),
            color=0x2E8B57
        )

        await ticket.send(interaction.user.mention, embed=embed)

        moved = await move_to_buero(interaction.user)

        if moved:
            await bot_speak(
                guild,
                f"Willkommen {interaction.user.display_name}. "
                f"Sie wurden in das Bewerbungsbüro verschoben. "
                f"Bitte beantworten Sie die Fragen im Ticket."
            )
        else:
            await bot_speak(
                guild,
                f"Neue Bundeswehr Bewerbung von {interaction.user.display_name} wurde erstellt."
            )

        logs = kanal(guild, "logs")
        await safe_send(logs, f"📋 Neue Bewerbung: {interaction.user.mention} → {ticket.mention}")

        await interaction.response.send_message(
            f"✅ Bewerbung erstellt: {ticket.mention}",
            ephemeral=True
        )


class BewerbungView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(BewerbungSelect())


@bot.event
async def on_ready():
    print(f"{bot.user} Ultra Bundeswehr System online!")

    bot.add_view(BewerbungView())

    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)} Commands geladen.")
    except Exception as e:
        print(f"SYNC FEHLER: {e}")


@bot.tree.command(name="setup", description="Erstellt wichtige Bot-Channels")
async def setup(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Keine Rechte.", ephemeral=True)

    channels = [
        "bewerbungs-check",
        "annahmen",
        "ablehnungen",
        "logs",
        "zello-funk",
        "bot-status"
    ]

    for ch in channels:
        if not kanal(interaction.guild, ch):
            await interaction.guild.create_text_channel(ch)

    await interaction.response.send_message("✅ Setup abgeschlossen.", ephemeral=True)


@bot.tree.command(name="bewerbung_panel", description="Sendet das Bewerbungspanel")
async def bewerbung_panel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Keine Rechte.", ephemeral=True)

    panel = interaction.guild.get_channel(PANEL_CHANNEL_ID)

    if not panel:
        return await interaction.response.send_message("❌ Panelchannel nicht gefunden.", ephemeral=True)

    embed = discord.Embed(
        title="📋 Bundeswehr Bewerbung",
        description=(
            "**Bundeswehr Bewerbungssystem**\n\n"
            "Klicke unten auf das Menü, um deine Bewerbung zu starten.\n"
            "Danach wird automatisch ein privates Bewerbungsticket erstellt."
        ),
        color=0x2E8B57
    )

    await panel.send(embed=embed, view=BewerbungView())
    await interaction.response.send_message("✅ Bewerbungspanel gesendet.", ephemeral=True)


@bot.tree.command(name="sagen", description="Bot spricht im Bewerbungsbüro")
async def sagen(interaction: discord.Interaction, text: str):
    await interaction.response.defer(ephemeral=True)
    await bot_speak(interaction.guild, text)
    await interaction.followup.send("🔊 Bot hat gesprochen.", ephemeral=True)


@bot.tree.command(name="debug_voice", description="Prüft Voice-Rechte und Join")
async def debug_voice(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    channel = interaction.guild.get_channel(BUERO_VOICE_CHANNEL_ID)

    if not channel:
        return await interaction.followup.send("❌ Büro Voicechannel nicht gefunden.", ephemeral=True)

    perms = channel.permissions_for(interaction.guild.me)

    text = (
        f"🔎 **Voice Debug**\n\n"
        f"Channel: {channel.name}\n"
        f"ID: {channel.id}\n\n"
        f"Kanal ansehen: {perms.view_channel}\n"
        f"Verbinden: {perms.connect}\n"
        f"Sprechen: {perms.speak}\n"
        f"Mitglieder verschieben: {perms.move_members}\n\n"
    )

    try:
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.move_to(channel)
        else:
            await asyncio.wait_for(channel.connect(), timeout=15)

        text += "✅ Bot konnte dem Büro beitreten."

    except Exception as e:
        text += f"❌ Join Fehler: `{e}`"

    await interaction.followup.send(text, ephemeral=True)


@bot.tree.command(name="voice_leave", description="Bot verlässt Voice")
async def voice_leave(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("✅ Bot hat Voice verlassen.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Bot ist in keinem Voice.", ephemeral=True)


@bot.tree.command(name="zello", description="Zeigt die Zello Funk Anleitung")
async def zello(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📻 Bundeswehr Zello Funk",
        description=(
            "📲 **Zello herunterladen**\n"
            "Android / iPhone / PC\n"
            "https://zello.com\n\n"
            "📷 **QR-Code scannen**\n"
            "➜ Zello öffnen\n"
            "➜ Kanal hinzufügen\n"
            "➜ QR-Code scannen\n\n"
            "🎤 **Funkname einstellen**\n"
            "Beispiele:\n"
            "• BW_Phil\n"
            "• BW_Max\n"
            "• BW_Leitung\n\n"
            "📡 **Funk Regeln**\n"
            "✅ Kurz sprechen\n"
            "✅ Kein Reinreden\n"
            "✅ Funkdisziplin\n"
            "✅ Keine Musik / Trolls"
        ),
        color=0x8B0000
    )

    try:
        file = discord.File("zello_qr.jpg", filename="zello_qr.jpg")
        embed.set_image(url="attachment://zello_qr.jpg")
        await interaction.response.send_message(embed=embed, file=file)
    except:
        await interaction.response.send_message(embed=embed)


@bot.tree.command(name="status", description="Zeigt Bot Status")
async def status(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 Bundeswehr Bot Status",
        color=0x2E8B57
    )

    embed.add_field(name="Bewerbungssystem", value="✅ Aktiv", inline=True)
    embed.add_field(name="Voice System", value="✅ Aktiv", inline=True)
    embed.add_field(name="Zello Hilfe", value="✅ Aktiv", inline=True)
    embed.add_field(name="Tickets", value="✅ Aktiv", inline=True)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="close", description="Schließt ein Bewerbungsticket")
async def close(interaction: discord.Interaction):
    if not interaction.channel.name.startswith("bewerbung-"):
        return await interaction.response.send_message("❌ Kein Bewerbungsticket.", ephemeral=True)

    await interaction.response.send_message("🔒 Ticket wird geschlossen.", ephemeral=True)
    await asyncio.sleep(3)
    await interaction.channel.delete()


@bot.tree.command(name="annehmen", description="Bewerber manuell annehmen")
async def annehmen(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.manage_channels:
        return await interaction.response.send_message("❌ Keine Rechte.", ephemeral=True)

    ch = kanal(interaction.guild, "annahmen")

    embed = discord.Embed(
        title="✅ Bewerbung manuell angenommen",
        description=f"{user.mention} wurde von {interaction.user.mention} angenommen.",
        color=0x00FF00
    )

    await safe_send(ch, embed=embed)
    await bot_speak(interaction.guild, f"Bewerbung von {user.display_name} wurde angenommen.")

    try:
        await user.send(embed=embed)
    except:
        pass

    await interaction.response.send_message("✅ Bewerber angenommen.", ephemeral=True)


@bot.tree.command(name="ablehnen", description="Bewerber manuell ablehnen")
async def ablehnen(interaction: discord.Interaction, user: discord.Member, grund: str = "Kein Grund angegeben"):
    if not interaction.user.guild_permissions.manage_channels:
        return await interaction.response.send_message("❌ Keine Rechte.", ephemeral=True)

    ch = kanal(interaction.guild, "ablehnungen")

    embed = discord.Embed(
        title="❌ Bewerbung manuell abgelehnt",
        description=f"{user.mention} wurde von {interaction.user.mention} abgelehnt.\n\nGrund: {grund}",
        color=0xFF0000
    )

    await safe_send(ch, embed=embed)
    await bot_speak(interaction.guild, f"Bewerbung von {user.display_name} wurde abgelehnt.")

    try:
        await user.send(embed=embed)
    except:
        pass

    await interaction.response.send_message("✅ Bewerber abgelehnt.", ephemeral=True)


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    await bot.process_commands(message)

    if not message.channel.name.startswith("bewerbung-"):
        return

    if message.channel.id in processing_tickets:
        return

    processing_tickets.add(message.channel.id)

    await message.channel.send(
        "🤖 Bewerbung erkannt.\n"
        "Ich warte jetzt **60 Sekunden** und prüfe danach automatisch."
    )

    await bot_speak(
        message.guild,
        f"Bewerbung von {message.author.display_name} wurde erkannt. Die Prüfung startet in sechzig Sekunden."
    )

    await asyncio.sleep(60)

    messages = []

    async for msg in message.channel.history(limit=50, oldest_first=True):
        if not msg.author.bot:
            messages.append(msg.content)

    text = "\n".join(messages)

    punkte, analyse, entscheidung, fehlend = bewerbung_check(text)

    check_channel = kanal(message.guild, "bewerbungs-check")

    check_embed = discord.Embed(
        title="🤖 Automatische Bewerbungsprüfung",
        color=0x3498DB
    )

    check_embed.add_field(name="👤 Bewerber", value=message.author.mention, inline=False)
    check_embed.add_field(name="📊 Bewertung", value=f"{punkte}/100", inline=True)
    check_embed.add_field(name="📌 Entscheidung", value=entscheidung, inline=True)
    check_embed.add_field(name="📝 Analyse", value="\n".join(analyse)[:1000], inline=False)
    check_embed.timestamp = datetime.now()

    await safe_send(check_channel, embed=check_embed)

    if entscheidung == "UNVOLLSTÄNDIG":
        await message.channel.send(
            "⚠️ Bewerbung unvollständig.\n"
            f"Fehlende Punkte: **{', '.join(fehlend)}**\n\n"
            "Bitte ergänze die fehlenden Antworten. Danach prüfe ich erneut."
        )

        await bot_speak(
            message.guild,
            f"Die Bewerbung von {message.author.display_name} ist unvollständig."
        )

        processing_tickets.discard(message.channel.id)
        return

    if entscheidung == "ANGENOMMEN":
        ziel = kanal(message.guild, "annahmen")
        titel = "✅ Bewerbung angenommen"
        farbe = 0x00FF00
        voice_text = f"Bewerbung von {message.author.display_name} wurde angenommen."
        dm_text = "Glückwunsch! Deine Bewerbung wurde angenommen."
    else:
        ziel = kanal(message.guild, "ablehnungen")
        titel = "❌ Bewerbung abgelehnt"
        farbe = 0xFF0000
        voice_text = f"Bewerbung von {message.author.display_name} wurde abgelehnt."
        dm_text = "Deine Bewerbung wurde leider abgelehnt."

    result = discord.Embed(title=titel, color=farbe)
    result.add_field(name="👤 Bewerber", value=message.author.mention, inline=False)
    result.add_field(name="📊 Bewertung", value=f"{punkte}/100", inline=True)
    result.add_field(name="📝 Analyse", value="\n".join(analyse)[:1000], inline=False)

    await safe_send(ziel, embed=result)
    await message.channel.send(embed=result)

    await bot_speak(message.guild, voice_text)

    try:
        dm = discord.Embed(
            title=titel,
            description=dm_text,
            color=farbe
        )
        dm.add_field(name="📊 Bewertung", value=f"{punkte}/100")
        dm.add_field(name="📝 Analyse", value="\n".join(analyse)[:1000], inline=False)
        await message.author.send(embed=dm)
    except:
        print("DM konnte nicht gesendet werden.")

    await message.channel.send("🔒 Ticket wird in **30 Sekunden** automatisch geschlossen.")

    await asyncio.sleep(30)

    try:
        await message.channel.delete()
    except Exception as e:
        print(f"LÖSCH FEHLER: {e}")

    processing_tickets.discard(message.channel.id)


bot.run(TOKEN)
