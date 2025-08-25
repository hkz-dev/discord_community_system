import discord
from discord.ext import commands
# import random 使わない
import asyncio
import configparser
import logging
import datetime
import traceback
import sys
import os
import mod_getPath #mod_getPath.py
import mod_db #mod_db.py

#!==========================================
#! navigator.pyが担当するユーザー検知イベント
#? なし
#!==========================================


#========================================================
# 対象チャンネルID
CHANNEL_ID =None
# token
BOT_TOKEN=None
#管理ユーザーID
ADMIN_USER_ID=None
#バージョン情報
VERSION=None
#バージョン日
VERSION_DATE=None
#個室リセットチャンネル
ROOM_RESET_CH_ID=None
#========================================================
# ログ出力

log_filePath = mod_getPath.get_navigator_logfile_path()
# ルートロガー取得
logger = logging.getLogger()
logger.setLevel(logging.INFO)
# フォーマット設定
fmt = "%(asctime)s : [%(levelname)-7s][%(filename)-15s][%(funcName)-40s] : %(message)s"
formatter = logging.Formatter(fmt)
# ファイルハンドラ
file_handler = logging.FileHandler(log_filePath, encoding="utf-8")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
# コンソール（標準出力）ハンドラ
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

#========================================================
# INI読み込み

ini_filePath = mod_getPath.get_inifile_path()
config = configparser.ConfigParser()
read_files = config.read(ini_filePath, encoding="utf-8")
if "admin" in config:
    ADMIN_USER_ID=config["admin"]["user_id"]
if "version" in config:
    VERSION=config["version"]["ver"]
    VERSION_DATE=config["version"]["date"]
if "navigator" in config:
    BOT_TOKEN      = config["navigator"]["token"]
    CHANNEL_ID = int(config["navigator"]["ch_id"])
if "reset_room" in config:
    ROOM_RESET_CH_ID = int(config["reset_room"]["ch_id"])

#========================================================
# BOT初期化

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)


#投稿IDからチャンネルIDを逆引き
async def get_channel_id_from_post_id(interaction, post_id):
    if post_id in (None, "なし"):
        return None
    guild = interaction.guild
    for channel in guild.text_channels:
        try:
            msg = await channel.fetch_message(int(post_id))
            if msg:
                return channel.id
        except discord.NotFound:
            pass
        except discord.Forbidden:
            pass
        except Exception as e:
            # ここでログに出すのもおすすめ
            logging.error(f"Error fetching message {post_id} in channel {channel.id}: {e}")
            pass
    return None

class StatusButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="確認する", style=discord.ButtonStyle.primary)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        logging.info(f"{interaction.user.id}がボタンをクリックしました")

        await interaction.response.defer(ephemeral=True)  # ✅ 応答保留しておく（タイムアウト防止）

        conn = None
        try:
            conn = mod_db.get_connection()
            result = mod_db.get_rec_tblUser(interaction.user.id, conn)

            if result:
                # データありの場合
                seq_no = result["seq_no"]
                join_dt = result["join_dt"]
                user_name = result["user_name"]
                user_nickname = result["user_nickname"]
                user_id = result["user_id"]
                room_name = result["room_name"]
                room_id = result["room_id"]
                first_reaction = result["first_reaction"]
                balance = result["balance"]
                last_reacted_post_id = result["last_reacted_post_id"]
                guild_id = interaction.guild.id
                today = datetime.datetime.now()
                delta = today - join_dt
                join_date_str = join_dt.strftime("%Y-%m-%d")
                days_since_join = delta.days + 1
                first_reaction_str = "未" if first_reaction == 0 else "済"
                last_reacted_post_channel_id = await get_channel_id_from_post_id(interaction, last_reacted_post_id)
                last_reacted_post_url = "なし"
                if last_reacted_post_channel_id is not None:
                    last_reacted_post_url = f"https://discord.com/channels/{guild_id}/{last_reacted_post_channel_id}/{last_reacted_post_id}"
                reset_url = f"https://discord.com/channels/{guild_id}/{ROOM_RESET_CH_ID}"
                if room_id:
                    room_url = f"https://discord.com/channels/{guild_id}/{room_id}"
                    room_info = (
                        f"[{room_name}]({room_url})\n\n"
                        f"※アクセスできない場合は削除されている可能性があります。\n"
                        f"{reset_url}でご確認ください。"
                    )
                else:
                    room_info = f"個室を取得できませんでした。\n{reset_url}で確認してください。"
                popular_posts = mod_db.get_rec_tblReactedhistory_top5(user_id, conn)
                popular_posts_str=None
                if popular_posts:
                    popular_post_urls = []
                    for post_id, ch_id in popular_posts:
                        url = f"https://discord.com/channels/{guild_id}/{ch_id}/{post_id}"
                        popular_post_urls.append(f"{url}")
                    popular_posts_str = "\n".join(popular_post_urls)
                else:
                    popular_posts_str = "記録なし"
                content = (
                    f"{user_nickname}({user_name})さんの現在のステータスは以下の通りです。:\n\n"
                    f"-ステータス-\n\n"
                    f"[残高]\n{balance} iso\n\n"
                    f"[最後にリアクションした投稿]\n{last_reacted_post_url}\n\n"
                    f"[よく反応されている投稿]\n{popular_posts_str}\n\n"
                    f"-基本情報-\n\n"
                    f"[初回ボーナス受領]\n{first_reaction_str}\n\n"
                    f"[加入日]\n{join_date_str} ({days_since_join}日目)\n\n"
                    f"[個室]\n{room_info}\n"
                )
            else:
                # 新規ユーザー処理
                user_id = interaction.user.id
                user_name = interaction.user.name
                user_nickname = interaction.user.nick or user_name

                dt = {
                    'join_dt': datetime.datetime.now(),
                    'user_id': user_id,
                    'user_name': user_name,
                    'user_nickname': user_nickname,
                    'room_id': None,
                    'room_name': None,
                    'first_reaction': 0,
                    'balance': 0,
                    'last_reacted_post_id': None
                }
                insert = mod_db.insert_rec_tblUser(dt, conn)
                if insert:
                    result = mod_db.get_rec_tblUser(interaction.user.id, conn)
                if result:
                    seq_no = result["seq_no"]
                    join_dt = result["join_dt"]
                    user_name = result["user_name"]
                    user_nickname = result["user_nickname"]
                    user_id = result["user_id"]
                    room_name = result["room_name"]
                    room_id = result["room_id"]
                    first_reaction = result["first_reaction"]
                    balance = result["balance"]
                    last_reacted_post_id = result["last_reacted_post_id"]
                    guild_id = interaction.guild.id
                    today = datetime.datetime.now()
                    delta = today - join_dt
                    join_date_str = join_dt.strftime("%Y-%m-%d")
                    days_since_join = delta.days + 1
                    first_reaction_str = "未" if first_reaction == 0 else "済"
                    last_reacted_post_channel_id = await get_channel_id_from_post_id(interaction, last_reacted_post_id)
                    last_reacted_post_url = "なし"
                    if last_reacted_post_channel_id is not None:
                        last_reacted_post_url = f"https://discord.com/channels/{guild_id}/{last_reacted_post_channel_id}/{last_reacted_post_id}"
                    room_url = f"https://discord.com/channels/{guild_id}/{ROOM_RESET_CH_ID}"
                    content = (
                        f"{user_nickname}({user_name})さんの現在のステータスは以下の通りです。:\n\n"
                        f"-ステータス-\n\n"
                        f"[残高]\n{balance} iso\n\n"
                        f"[最後にリアクションした投稿]\n{last_reacted_post_url}\n\n"
                        f"[よく反応されている投稿]\n記録なし\n\n"
                        f"-基本情報-\n\n"
                        f"[初回ボーナス受領]\n{first_reaction_str}\n\n"
                        f"[加入日]\n{join_date_str} ({days_since_join}日目)\n\n"
                        f"[個室]\n個室を取得できませんでした。\n{room_url}で確認してください。\n\n"
                    )
                else:
                    content = "ユーザー情報を取得できませんでした。管理者に連絡してください。"
            # ✅ 応答を followup で送信
            await interaction.followup.send(content, ephemeral=True)
            logging.info(f"{interaction.user.name}さん:({interaction.user.id})にステータスを返信しました。")

        finally:
            if conn:
                conn.close()


async def create_post():
    channel = bot.get_channel(CHANNEL_ID)
    if channel is not None:
        #投稿全削除
        await channel.purge(limit=10)
        embed = discord.Embed(
            title=f"【マイステータス】Ver.{VERSION} ({VERSION_DATE})",
            description=(f"ボタンクリックで、現在のあなたのステータスを確認できます。"),
            color=discord.Color.blue()
        )
        view = StatusButton()
        await channel.send(embed=embed, view=view)
    else:
        print("チャンネルが見つかりませんでした")


@bot.event
async def on_ready():
    logging.info(f'ログインしました: {bot.user}')
    try:
        conn = mod_db.get_connection()
        conn.close()
        logging.info(f"DB接続確認成功：{conn}")
        await create_post()
    except Exception as e:
        logging.error(f"DB接続に失敗しました: {e}")



#管理者へエラー通知
async def notify_admin(error_message):
    try:
        admin_user = await bot.fetch_user(ADMIN_USER_ID)
        msg=f"🚨Botでエラーが発生しました。エラーを確認し、再度実行してください。\n```{error_message}```"
        logging.error(msg)
        await admin_user.send(msg)
        logging.error("=====停止中=====")
    except Exception as notify_error:
        logging.error(f"管理者通知に失敗: {notify_error}")

@bot.event
async def on_error(event, *args, **kwargs):
    exc_type, exc_value, exc_tb = sys.exc_info()
    tb_list = traceback.extract_tb(exc_tb)
    # エラーが起きたフレーム（最後のフレーム）
    last_frame = tb_list[-1] if tb_list else None
    # 呼び出し元フレーム（1つ前）
    caller_frame = tb_list[-2] if len(tb_list) >= 2 else None
    # 各情報を取得
    filename = os.path.basename(last_frame.filename) if last_frame else "不明ファイル"
    funcname = last_frame.name if last_frame else "不明関数"
    lineno = last_frame.lineno if last_frame else "不明行"
    caller_funcname = caller_frame.name if caller_frame else "不明呼び出し元"
    # 例外メッセージを取得
    error_message = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
    # 整形メッセージ作成
    formatted_message = (
        f"【エラー発生情報】\n"
        f"ファイル名: {filename}\n"
        f"関数名: {funcname}\n"
        f"呼び出し元関数名: {caller_funcname}\n"
        f"行番号: {lineno}\n"
        f"\n【エラーメッセージ】\n"
        f"{error_message}"
    )
    logging.error(f"イベントでエラー発生: {event}\n{formatted_message}")
    await notify_admin(formatted_message)


async def run_bot():
        await bot.start(BOT_TOKEN)

if __name__ == "__main__":
    logging.info("run!")
    asyncio.run(run_bot())