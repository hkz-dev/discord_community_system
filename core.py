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
#! core.pyが担当するユーザー検知イベント
#? on_message()
#? on_message_delete()
#? on_reaction_add()
#? on_reaction_remove()
#? on_member_update()
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

#投稿したら付与
POST=None
#リアクションされたら付与
GET=None
#リアクションしたら付与
GIVE=None
#初回ボーナス投稿ID
FIRST_GET_POST_ID=None
#初回ボーナス額
FIRST_GET=None
#個室カテゴリID 再生成用に使います
ROOM_CATEGORY_ID=None
#========================================================
# ログ出力

log_filePath = mod_getPath.get_core_logfile_path()
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
if "core" in config:
    BOT_TOKEN = config["core"]["token"]
if "isoMint" in config:
    POST				=int(config["isoMint"]["post"])
    GET					=int(config["isoMint"]["get"])
    GIVE				=int(config["isoMint"]["give"])
    FIRST_GET_POST_ID	=config["isoMint"]["first_get_post_id"]
    FIRST_GET			=int(config["isoMint"]["first_get"])
if "roomer" in config:
    ROOM_CATEGORY_ID = int(config["roomer"]["category_id"])


#========================================================
# BOT初期化

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.reactions = True
intents.guild_reactions = True  # 追加
bot = commands.Bot(command_prefix="!", intents=intents)





#投稿イベント
@bot.event
async def on_message(message):
    logging.info(f"投稿イベント")
    user = message.author
    user_name = user.name
    user_nickname =user.nick
    if not user_nickname:
        user_nickname=user_name
    discriminator = user.discriminator  # 4桁の番号
    user_id = user.id
    is_bot = user.bot  # Botかどうか
    if message.guild is None:
        logging.info(f"DMのため無視")
        logging.info(mod_logMsg.okend)
        return
    if is_bot:
        logging.info(f"botによる投稿のため無視")
        logging.info(mod_logMsg.okend)
        return
    conn=None
    added = None
    try:
        conn=mod_db.get_connection()
        ur=mod_db.get_rec_tblUser(user_id,conn)
        if not ur:
            #作ろう
            dt={
                'join_dt':datetime.datetime.now(),
                'user_id':user_id,
                'user_name':user_name,
                'user_nickname':user_nickname,
                'room_id':None,
                'room_name':None,
                'first_reaction':0,
                'balance':0,
                'last_reacted_post_id':None
            }
            insert = mod_db.insert_rec_tblUser(dt,conn)
            if insert:
                ur=mod_db.get_rec_tblUser(user_id,conn)
            else:
                logging.error(f"ユーザーレコードの初期値を作成できませんでした")
                logging.error(mod_logMsg.ngend)
                return
        added=mod_db.update_tblUser_byKey(user_id,'balance',ur['balance']+POST,conn)
        if added:
            logging.info(f"user_id:{user_id}(投稿主)のbalanceを更新しました")
            logging.info(mod_logMsg.okend)
            return
        else:
            logging.error(f"user_id:{user_id}(投稿主)のbalanceを更新できませんでした")
            logging.error(mod_logMsg.ngend)
            return
    finally:
        if conn:
            conn.close()
            logging.info(mod_logMsg.dbconend)


@bot.event
async def on_message_delete(message):
    logging.info(f"投稿削除イベント")
    if message.guild is None: #DMの場合
        logging.info("DMのため無視")
        logging.info(mod_logMsg.okend)
        return
    if message.author is None: #authorが取得できない場合
        logging.error("投稿主情報が取得できませんでした")
        logging.error(mod_logMsg.ngend)
        return
    user = message.author
    user_id = user.id
    if user.bot:#botだったら
        logging.info(f"botによる投稿のため無視")
        logging.info(mod_logMsg.okend)
        return
    conn = None
    try:
        conn=mod_db.get_connection()
        ur=mod_db.get_rec_tblUser(user_id,conn)
        added=mod_db.update_tblUser_byKey(user_id,'balance',ur['balance']-POST,conn)
        if added:
            logging.info(f"user_id:{user_id}のbalanceを更新しました")
            logging.info(mod_logMsg.okend)
            return
    except Exception as e:
        logging.error(f"DB更新中にエラー: {e}")
    finally:
        if conn:
            conn.close()
            logging.info(mod_logMsg.dbconend)


def create_new_room(guild):
    category = guild.get_channel(ROOM_CATEGORY_ID)
    existing_names = [ch.name for ch in category.channels]
    while True:
        num = random.randint(100000, 999999)
        channel_name = f"room-{num}"
        if channel_name not in existing_names:
            return channel_name

async def create_user_record_with_room(conn, guild, member, u_id, u_name, u_nickname):
    if not u_nickname:
        #ユーザー名と同じにする
        u_nickname = u_name
    room_category=guild.get_channel(ROOM_CATEGORY_ID)
    if room_category is None:
        logging.error(f"個室カテゴリが見つかりませんでした。")
        logging.error(mod_logMsg.rf)
        return False
    room_name = create_new_room(guild)
    #チャンネル作成：最初は誰でも読めるが書き込み不可
    overwrites = {guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False)}
    try:
        channel = await guild.create_text_channel(
            name=room_name,
            category=room_category,
            overwrites=overwrites,
            reason=f"{member.name} の個別チャンネル作成"
        )
    except discord.Forbidden:
        logging.error("チャンネル作成権限がありません。")
        logging.error(mod_logMsg.rf)
        return False
    except discord.HTTPException as e:
        logging.error(f"チャンネル作成に失敗しました: {e}")
        logging.error(mod_logMsg.rf)
        return False
    logging.info(f"{room_name} を作成しました。ユーザーレコードを追加します")
    #部屋idと部屋名get
    room_id=channel.id
    room_name=channel.name
    dt={
        'join_dt':datetime.datetime.now(),
        'user_id':u_id,
        'user_name':u_name,
        'user_nickname':u_nickname,
        'room_id':room_id,
        'room_name':room_name,
        'first_reaction':0,
        'balance':0,
        'last_reacted_post_id':None
    }
    result = mod_db.insert_rec_tblUser(dt,conn)
    #書き込み権限を与える
    if result:
        await channel.set_permissions(
            member,
            read_messages=True,
            send_messages=True
        )
        logging.info(f"個室を作成し、ユーザーレコードを追加しました")
        logging.info(f"イレギュラー生成のため、ユーザーに対する個室作成DMの送信は行いません")
        logging.info(mod_logMsg.rt)
        return True
    else:
        logging.error(f"個室は作成しましたが、ユーザーレコードを追加できませんでした")
        logging.error(mod_logMsg.rf)
        return False

@bot.event
async def on_raw_reaction_add(payload):
    logging.info(f"user_id:{payload.user_id} が {payload.emoji} を追加しました")
    # チャンネル取得
    channel = bot.get_channel(payload.channel_id)
    if channel is None:
        logging.warning("チャンネルが取得できません")
        return
    # メッセージ取得
    try:
        message = await channel.fetch_message(payload.message_id)
    except Exception as e:
        logging.error(f"メッセージ取得失敗: {e}")
        logging.error(mod_logMsg.ngend)
        return
    guild = bot.get_guild(payload.guild_id)
    # 投稿主
    author = message.author
    author_id = author.id
    author_member = await guild.fetch_member(author_id)
    author_name = author_member.name
    author_nickname = author_member.nick
    #反応主
    reactor_id = payload.user_id
    reactor_member = await guild.fetch_member(reactor_id)
    reactor_name = reactor_member.name
    reactor_nickname = reactor_member.nick
    if author_id == reactor_id:
        logging.info("自分自身の投稿へのリアクションのため無効")
        logging.info(mod_logMsg.okend)
        return
    if author.bot:
        logging.info("Botの投稿へのリアクションのため無効")
        logging.info(mod_logMsg.okend)
        return
    #投稿ID
    post_id = str(payload.message_id)
    try:
        conn=mod_db.get_connection()
        #リアクションしたユーザー
        reactor_rec = mod_db.get_rec_tblUser(reactor_id,conn)
        if not reactor_rec:
            #存在しないので作ろう
            if await create_user_record_with_room(conn, guild, reactor_member, reactor_id, reactor_name, reactor_nickname):
                #再取得
                reactor_rec = mod_db.get_rec_tblUser(reactor_id,conn)
                if not reactor_rec:
                    logging.error(f"レコード再取得できませんでした")
                    logging.error(mod_logMsg.ngend)
                    return
            else:
                logging.error(f"レコードを作成できませんでした")
                logging.error(mod_logMsg.ngend)
                return
        #logging.info(reactor_rec)
        #投稿主
        author_rec =mod_db.get_rec_tblUser(author_id,conn)
        if not author_rec:
            #存在しないので作ろう
            if await create_user_record_with_room(conn, guild, author_member, author_id, author_name, author_nickname):
                #再取得
                author_rec = mod_db.get_rec_tblUser(author_id,conn)
                if not author_rec:
                    logging.error(f"レコード再取得できませんでした")
                    logging.error(mod_logMsg.ngend)
                    return
            else:
                logging.error(f"レコードを作成できませんでした")
                logging.error(mod_logMsg.ngend)
                return
        #logging.info(author_rec)
        #ここに来る時点でtblUserには必ずユーザーレコードがある状態 個室もある-------------------------
        #連続ならreturn
        if post_id == reactor_rec['last_reacted_post_id']:
            #同じ投稿に連続でリアクションした
            logging.info(f"同じ投稿に連続でリアクションをしているので無効")
            logging.info(mod_logMsg.okend)
            return
        if reactor_rec['first_reaction'] == 0 and post_id == FIRST_GET_POST_ID:
            #ボーナス投稿への初のリアクション
            #更新
            #first_reactionに1を立てる
            if mod_db.update_tblUser_byKey(reactor_id, 'first_reaction', 1, conn):
                logging.info(f"user_id:({reactor_id})のfirst_reactionを1にしました")
            else:
                logging.error(f"user_id:({reactor_id})のfirst_reactionを1にできませんでした return")
                logging.error(mod_logMsg.ngend)
                return
            #最後にリアクションした投稿を保存
            if mod_db.update_tblUser_byKey(reactor_id, 'last_reacted_post_id', post_id, conn):
                logging.info(f"user_id:({reactor_id})のlast_reacted_post_idを更新しました")
            else:
                logging.error(f"user_id:({reactor_id})のlast_reacted_post_idを更新できませんでした")
                logging.error(mod_logMsg.ngend)
                return
            #ポイント付与
            if mod_db.update_tblUser_byKey(reactor_id, 'balance', reactor_rec['balance'] + FIRST_GET, conn):
                logging.info(f"user_id:({reactor_id})のbalanceを更新しました")
            else:
                logging.error(f"user_id:({reactor_id})のbalanceを更新できませんでした")
                logging.error(mod_logMsg.ngend)
                return
            #リアクション履歴を保存
            if mod_db.insert_tblReactedHistory(datetime.datetime.now(),post_id,author_id,reactor_id,channel.id,conn):
                logging.info(f"リアクション履歴を保存しました。")
            else:
                logging.error(f"リアクション履歴を保存できませんでした")
                logging.error(mod_logMsg.ngend)
                return
            # 全部成功したらメッセージを送ってreturn
            try:
                msg=(
                    f"🎉リアクションボーナスを獲得しました！\n"
                    f"[{FIRST_GET}]iso付与\n"
                    f"この[iso]というのは、ここで使える通貨です。\n"
                    f"1:投稿する\n"
                    f"2:誰かの投稿にリアクションする\n"
                    f"3:誰かに投稿をリアクションされる\n"
                    f"ことで加算されていきます。\n"
                    f"\n"
                    f"\n"
                    f"貯めておくと、良いことがあるかも！！（開発中です）"
                )
                await reactor_member.send(msg)
                logging.info(f"user_id:({reactor_id})にDMを送信しました")
                logging.info(mod_logMsg.okend)
                return
            except Exception as e:
                logging.warning(f"user_id:({reactor_id}) にDMを送れませんでした: {e}")
                logging.error(mod_logMsg.ngend)
                return
        else:
            #初回ボーナスへの投稿ではない
            #投稿主に付与
            if mod_db.update_tblUser_byKey(author_id,'balance',author_rec['balance']+GET,conn):
                logging.info(f"user_id:({author_id})(投稿主)のbalanceを更新しました")
            else:
                logging.error(f"user_id:({author_id})(投稿主)のbalanceを更新できませんでした")
                logging.error(mod_logMsg.ngend)
                return
            #リアクションした人に付与
            if mod_db.update_tblUser_byKey(reactor_id,'balance',reactor_rec['balance']+GIVE,conn):
                logging.info(f"user_id:({reactor_id})(反応主)のbalanceを更新しました")
            else:
                logging.error(f"user_id:({reactor_id})(反応主)のbalanceを更新できませんでした")
                logging.error(mod_logMsg.ngend)
                return
            #最後にリアクションした投稿を保存
            if mod_db.update_tblUser_byKey(reactor_id,'last_reacted_post_id',post_id,conn):
                logging.info(f"user_id:({author_id})(反応主)のlast_reacted_post_idを更新しました")
            else:
                logging.error(f"user_id:({author_id})(反応主)のlast_reacted_post_idを更新できませんでした")
                logging.error(mod_logMsg.ngend)
                return
            #リアクション履歴を保存
            if mod_db.insert_tblReactedHistory(datetime.datetime.now(),post_id,author_id,reactor_id,channel.id,conn):
                logging.info(f"リアクション履歴を保存しました。")
                logging.info(mod_logMsg.okend)
                return
            else:
                logging.error(f"リアクション履歴を保存できませんでした")
                logging.error(mod_logMsg.ngend)
                return
    finally:
        if conn:
            conn.close()




@bot.event
async def on_reaction_remove(reaction, user):
    logging.info(f"{user} が {reaction.emoji} を削除しました")


@bot.event
async def on_member_update(before, after):
    logging.info(f"{before.display_name} から {after.display_name} に更新")



@bot.event
async def on_ready():
    logging.info(f'ログインしました:{bot.user}')
    try:
        conn = mod_db.get_connection()
        if conn:
            conn.close()
            logging.info(f"DB接続確認成功：{conn}")
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