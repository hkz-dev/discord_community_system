import discord
from discord.ext import commands
import random
import asyncio
import configparser
import logging
import datetime
import traceback
import sys
import os
import mod_getPath #mod_getPath.py
import mod_db #mod_db.py
import mod_logMsg #mod_logMsg.py

#!==========================================
#! roomer.pyが担当するユーザー検知イベント
#? on_member_join()
#!==========================================


#========================================================
# 個室カテゴリ
ROOM_CATEGORY_ID =None
# token
BOT_TOKEN=None
#管理ユーザーID
ADMIN_USER_ID=None
#バージョン情報
VERSION=None
#バージョン日
VERSION_DATE=None
#個室リセット用チャンネルID
ROOM_RESET_CH_ID=None
#========================================================
# ログ出力

log_filePath = mod_getPath.get_roomer_logfile_path()
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
    ADMIN_USER_ID = config["admin"]["user_id"]
if "version" in config:
    VERSION=config["version"]["ver"]
    VERSION_DATE=config["version"]["date"]
if "roomer" in config:
    BOT_TOKEN = config["roomer"]["token"]
    ROOM_CATEGORY_ID = int(config["roomer"]["category_id"])
if "reset_room" in config:
    ROOM_RESET_CH_ID = int(config["reset_room"]["ch_id"])

#========================================================
# BOT初期化

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)




import discord

async def send_DM_to_member(member, user_name, channel_link, type):
    #type
    # 0=新規ユーザーの入室
    # 1=出戻りユーザーの入室+チャンネル残っていた
    # 2=出戻りユーザーの入室+チャンネル残っていなかった
    try:
        if type == 0:
            await member.send(
                f"ようこそ！\n"
                f"{user_name}さん専用の壁打ちチャンネルを用意しました。\n"
                f"壁打ちチャンネルは、{channel_link}です。\n"
                f"思考の置き場としてご自由にお使いください！"
            )
            logging.info(f"DMを[{member.name}]に送信しました。(新規ユーザー&チャンネル新規作成)")
            logging.info(mod_logMsg.rt)
            return True
        elif type == 1:
            await member.send(
                f"おかえりなさい！\n"
                f"{user_name}さんが在籍していたころの壁打ちチャンネルがまだ残っていました！\n"
                f"書き込み権限を再付与しましたので、引き続きお使いいただけます。\n"
                f"現在の壁打ちチャンネルは、{channel_link}です。"
            )
            logging.info(f"DMを[{member.name}]に送信しました。(出戻りユーザー&チャンネルあり)")
            logging.info(mod_logMsg.rt)
            return True
        elif type == 2:
            await member.send(
                f"おかえりなさい！\n"
                f"{user_name}さんが在籍していたころの壁打ちチャンネルは削除されてしまいました。\n"
                f"新規で作成しましたので、こちらをご利用ください。\n"
                f"現在の壁打ちチャンネルは、{channel_link}です。"
            )
            logging.info(f"DMを[{member.name}]に送信しました。(出戻りユーザー&チャンネル無し新規作成)")
            logging.info(mod_logMsg.rt)
            return True
    except discord.Forbidden:
        logging.warning(f"DMを[{member.name}]に送信できませんでした：DM拒否またはブロックされています。")
        logging.error(mod_logMsg.rf)
        return False
    except discord.HTTPException as e:
        logging.error(f"DM送信中にHTTPエラーが発生しました：{e}")
        logging.error(mod_logMsg.rf)
        return False
    except Exception as e:
        logging.exception(f"DM送信中に予期しないエラーが発生しました：{e}")
        logging.error(mod_logMsg.rf)
        return False




def create_new_channel_name(member):
    category = member.guild.get_channel(ROOM_CATEGORY_ID)
    existing_names = [ch.name for ch in category.channels]
    while True:
        num = random.randint(100000, 999999)
        channel_name = f"room-{num}"
        if channel_name not in existing_names:
            return channel_name


@bot.event
async def on_member_join(member):
    #botが入ってきた
    if member.bot :
        logging.info(f"botが入室しました。処理を終了します(return)")
        return
    else:
        #botではない
        #初期値生成
        join_dt                 =datetime.datetime.now()
        user_id                 =str(member.id)
        user_name               =str(member.name)
        user_nickname           =str(member.nick if member.nick else user_name)
        room_id                 =None
        room_name               =None
        first_reaction          =0
        balance                 =0
        last_reacted_post_id    =None
        #入室ログ出し
        logging.info(f"ユーザーが入室しました。user_id:({user_id}),user_name:({user_name}),user_nickname:({user_nickname})")
        guild=member.guild
        room_category=guild.get_channel(ROOM_CATEGORY_ID)
        if room_category is None:
            logging.error(f"個室カテゴリが見つかりませんでした。処理を終了します")
            logging.error(mod_logMsg.ngend)
            return
        try:
            conn=mod_db.get_connection()
            ur=mod_db.get_rec_tblUser(user_id,conn)
            if ur:
                #ユーザーレコードあり→出戻り勢
                logging.info(f"user_id({ur['user_id']})が見つかりました。個室の存在確認を行います")
                room_id = ur['room_id']
                room_name = ur['room_name']
                room_ch = guild.get_channel(int(room_id)) if room_id else None
                if room_ch is None:
                    #個室無し
                    logging.info(f"個室名:{room_name}({room_id})が残っていませんでした。DBのroom_nameとroom_idをクリアしたのち、チャンネル新規作成および権限付与処理を行います")
                    #クリア
                    mod_db.update_tblUser_byKey(user_id,'room_id','',conn)
                    mod_db.update_tblUser_byKey(user_id,'room_name','',conn)
                    # 新規チャンネル名作成
                    room_name = create_new_channel_name(member)
                    overwrites = {
                        member.guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False)
                    }
                    channel = await member.guild.create_text_channel(
                        name=room_name,
                        category=room_category,
                        overwrites=overwrites,
                        reason=f"{member.name} の個別チャンネル再作成"
                    )
                    logging.info(f"{room_name} を再作成しました。DBのroom_name,room_idを更新します")
                    #更新
                    mod_db.update_tblUser_byKey(user_id,'room_id',channel.id,conn)
                    mod_db.update_tblUser_byKey(user_id,'room_name',room_name,conn)
                    await channel.set_permissions(
                            member,
                            read_messages=True,
                            send_messages=True
                        )
                    logging.info(f"[{member.name}]に[{room_name}]チャンネルの書き込み権限を付与しました")
                    guild_id = member.guild.id
                    channel_link = f"https://discord.com/channels/{guild_id}/{channel.id}"
                    if await send_DM_to_member(member,user_name,channel_link,2):
                        logging.info(mod_logMsg.okend)
                        return
                    else:
                        logging.error(mod_logMsg.ngend)
                        return
                else:
                    #個室あり 権限再付与のみ
                    logging.info(f"個室名:{room_name}({room_id})が残っていました。チャンネル新規作成は行わず、権限付与処理のみ行います")
                    await channel.set_permissions(
                        member,
                        read_messages=True,
                        send_messages=True
                    )
                    logging.info(f"[{member.name}]に[{room_name}]チャンネルの書き込み権限を再付与しました")
                    guild_id = member.guild.id
                    channel_link = f"https://discord.com/channels/{guild_id}/{channel.id}"
                    if await send_DM_to_member(member,user_name,channel_link,1):
                        logging.info(mod_logMsg.okend)
                        return
                    else:
                        logging.error(mod_logMsg.ngend)
                        return
            else:
                #レコードが見つからなかったので、新規
                room_name = create_new_channel_name(member)
                #チャンネル作成：最初は誰でも読めるが書き込み不可
                overwrites = {guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False)}
                channel = await guild.create_text_channel(
                    name=room_name,
                    category=room_category,
                    overwrites=overwrites,
                    reason=f"{member.name} の個別チャンネル作成"
                )
                logging.info(f"{room_name} を作成しました。ユーザーレコードを追加します")
                #部屋idと部屋名get
                room_id=channel.id
                room_name=channel.name
                dt={
                    'join_dt':join_dt,
                    'user_id':user_id,
                    'user_name':user_name,
                    'user_nickname':user_nickname,
                    'room_id':room_id,
                    'room_name':room_name,
                    'first_reaction':first_reaction,
                    'balance':balance,
                    'last_reacted_post_id':last_reacted_post_id
                }
                result = mod_db.insert_rec_tblUser(dt,conn)
                #書き込み権限を与える
                if result:
                    await channel.set_permissions(
                        member,
                        read_messages=True,
                        send_messages=True
                    )
                    logging.info(f"[{member.name}]に[{room_name}]チャンネルの書き込み権限を付与しました")
                    guild_id = member.guild.id
                    channel_link = f"https://discord.com/channels/{guild_id}/{channel.id}"
                    if await send_DM_to_member(member,user_name,channel_link,0):
                        logging.info(mod_logMsg.okend)
                        return
                    else:
                        logging.error(mod_logMsg.ngend)
                        return
        finally:
            if conn:
                conn.close()
            return




class RegenerateRoomButton(discord.ui.View):
    def __init__(self, channel, member, uid, uname, unick):
        super().__init__(timeout=60)
        self.channel = channel
        self.member = member
        self.uid = uid
        self.uname = uname
        self.unick = unick
    @discord.ui.button(label="再生成する", style=discord.ButtonStyle.danger)
    async def regenerate(self, interaction: discord.Interaction, button: discord.ui.Button):
        #再生成処理
        #既存は削除
        if self.channel is not None:
            await self.channel.delete()
        guild=self.member.guild
        room_category=guild.get_channel(ROOM_CATEGORY_ID)
        room_name = create_new_channel_name(self.member)
        overwrites = {
            self.member.guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False)
        }
        channel = await self.member.guild.create_text_channel(
            name=room_name,
            category=room_category,
            overwrites=overwrites,
            reason=f"{self.member.name} の個別チャンネル再作成"
        )
        await channel.set_permissions(
                self.member,
                read_messages=True,
                send_messages=True
            )
        room_id=channel.id
        conn=mod_db.get_connection()
        ur = mod_db.get_rec_tblUser(self.uid,conn)
        nickname = None
        if self.unick is None:
            nickname=self.uname
        if not ur:
            logging.info(f"ユーザーレコードが無いので生成します")
            dt={
                'join_dt':datetime.datetime.now(),
                'user_id':self.uid,
                'user_name':self.uname,
                'user_nickname':nickname,
                'room_id':room_id,
                'room_name':room_name,
                'first_reaction':0,
                'balance':0,
                'last_reacted_post_id':None
            }
            if mod_db.insert_rec_tblUser(dt,conn):
                await interaction.response.send_message(
                    f"個室を再生成しました。\n"
                    f"今後はこちらをお使いください。\n"
                    f"{channel.mention}",
                    ephemeral=True
                )
                logging.info(mod_logMsg.okend)
                return
        else:
            #ユーザーレコードあるので更新のみ
            if mod_db.update_tblUser_byKey(self.uid,'room_id',room_id,conn):
                if mod_db.update_tblUser_byKey(self.uid,'room_name',room_name,conn):
                    #update完了 返信する
                    await interaction.response.send_message(
                        f"個室を再生成しました。\n"
                        f"今後はこちらをお使いください。\n"
                        f"{channel.mention}",
                        ephemeral=True
                    )
                    logging.info(mod_logMsg.okend)
                    return
                else:
                    logging.error(f"tblUserのroom_nameを更新できませんでした")
                    logging.error(mod_logMsg.ngend)
                    return
            else:
                logging.error(f"tblUserのroom_idを更新できませんでした")
                logging.error(mod_logMsg.ngend)
                return

# ボタンのビュー
class RoomStatusButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # ボタンがずっと有効になる
    @discord.ui.button(label="確認する", style=discord.ButtonStyle.primary)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        logging.info(f"{interaction.user.id}がボタンをクリックしました")
        uid=interaction.user.id
        uname=interaction.user.name
        unick=interaction.user.nick
        guild = interaction.guild
        member = interaction.user
        # ROOM_CATEGORY_ID を使ってカテゴリを取得
        room_category = guild.get_channel(ROOM_CATEGORY_ID)
        if not room_category:
            logging.error(f"個室カテゴリが見つかりませんでした。")
            logging.error(mod_logMsg.ngend)
            return
        #uidがROOM_CATEGORYカテゴリ内のチャンネルで、書き込み権限を持っているroomチャンネルがあるかを確認する
        existing_room = None
        for channel in room_category.text_channels:
            perms = channel.permissions_for(member)
            if perms.send_messages:
                existing_room = channel
                break
        if existing_room:
            # 個室が既にある場合は確認ボタン付きのメッセージを送信
            await interaction.response.send_message(
                f"あなたの個室 {existing_room.mention} は既に存在します。再生成しますか？\n再生成しない場合は、そのまま退出してください。\nこのボタンは60秒間有効です。",
                view=RegenerateRoomButton(existing_room, member, uid, uname, unick),
                ephemeral=True
            )
            return
        else:
            # 個室が既にある場合は確認ボタン付きのメッセージを送信
            await interaction.response.send_message(
                f"個室が見つかりませんでした。\n再生成する場合は、「再生成する」をクリックしてください。\nこのボタンは60秒間有効です。",
                view=RegenerateRoomButton(existing_room, member, uid, uname, unick),
                ephemeral=True
            )
            return
        conn=mod_db.get_connection()
        urec=mod_db.get_rec_tblUser(uid,conn)



async def create_room_reset_post():
    channel = bot.get_channel(ROOM_RESET_CH_ID)
    if channel is not None:
        #投稿全削除
        await channel.purge(limit=10)
        embed = discord.Embed(
            title=f"【個室リセット】Ver.{VERSION} ({VERSION_DATE})",
            description=(
                f"ボタンクリックで、現在のあなたの個室の状態を確認できます。\n"
                        ),
            color=discord.Color.blue()
        )
        view = RoomStatusButton()
        await channel.send(embed=embed, view=view)
    else:
        print("チャンネルが見つかりませんでした")


@bot.event
async def on_ready():
    logging.info(f'ログインしました: {bot.user}')
    try:
        conn = mod_db.get_connection()
        if conn:
            conn.close()
            logging.info(f"DB接続確認成功：{conn}")
            await create_room_reset_post()
        else:
            logging.error("DB接続が取得できませんでした。")
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