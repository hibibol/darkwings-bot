import discord
from  discord.ext import tasks
from datetime import datetime, timedelta, timezone
import os

from urllib import request
from bs4 import BeautifulSoup

from route import RouteChecker
from route import GspreadHandler
from const import *
import json
import numpy
#テロに必要
import random
import glob


unchi = "💩"


# 接続に必要なオブジェクトを生成
client = discord.Client()

JST = timezone(timedelta(hours=+9), 'JST')

with open(json_file,"r") as f:
    manage_dict = json.load(f)

with open("config.json","r") as f:
    TOKEN = json.load(f)["DISCORD_TOKEN"]

print(TOKEN)

#manage_dict["count"] =0

class Boss:
    def __init__(self,name,hp):
        self.hp = hp
        self.name = name

boss_list_n= [Boss("ゴブリングレート",600),Boss("ライライ",800),Boss("ムシュフシュ",1000),Boss("マスター・センリ",1200),Boss("アルゲティ",1500)]
boss_list_vh= [Boss("ゴブリングレート",700),Boss("ライライ",900),Boss("ムシュフシュ",1200),Boss("マスター・センリ",1400),Boss("アルゲティ",1700)]


def create_bosyu_message(boss_supress_number,reserve_dict):

    lap_number = boss_supress_number//5 +1
    text = f"{str(lap_number)}週目 現在のボスの状況は以下の通りです。\n"

#    if boss_supress_number < 48 :
    text += "**" + boss_list_n[boss_supress_number%5].name +"**\n"\
            +"残HP:"+'{:,}'.format(reserve_dict["remain_hp"]) +"万\n"
    
    text +="凸終了後予定残HP:"+'{:,}'.format(reserve_dict[str(boss_supress_number%5)]["plan_remain_hp"])+"万\n"\
        +"[凸予定者]" +"\n"
    totsus = reserve_dict["totsu"].split("\t")
    text += create_reserve_message_for_each_boss(reserve_dict[str(boss_supress_number%5)],totsu_list=totsus)
    text += "\n[凸予約状況]"
    for i in range(1,5):
        text+= "\n"+boss_list_vh[(boss_supress_number+i)%5].name + "\n"\
            +"凸終了後予定残HP:"+'{:,}'.format(reserve_dict[str((boss_supress_number+i)%5)]["plan_remain_hp"])+"万\n"
        text += create_reserve_message_for_each_boss(reserve_dict[str((boss_supress_number+i)%5)])

    return text


def create_reserve_message_for_each_boss(reserve_each_dict,totsu_list=False):
    member_list = reserve_each_dict["members"].split("\t")
    damage_list = reserve_each_dict["damages"].split("\t")
    over_list = reserve_each_dict["over"].split("\t")

    members_number = len(member_list) -1
    text = ""
    for i in range(members_number):
        line = "\t" + member_list[i] + " " + str(damage_list[i]) + "万"
        if len(over_list)-1 > i:
            if member_list[i] == over_list[i]:
                line += " 持ち越し"
        if totsu_list:
            if member_list[i] in totsu_list:
                line += " 凸中"
        text += f"{line}\n"
    return text

def initialize_reserve(reserve_each_dict,default_hp):
    new_dict = reserve_each_dict
    new_dict["members"] = ""#タブ区切りの文字列を入れていく
    new_dict["damages"] =""#タブ区切りの文字列を入れていく
    new_dict["ids"] = ""#タブ区切りの文字列を入れていく
    new_dict["plan_remain_hp"] = default_hp
    new_dict["over"] = ""#タブ区切りの文字列を入れていく
    return new_dict

def calc_remain_hp(default_hp,damage_list):
    remain_hp = default_hp
    for i in range(len(damage_list)-1):
        remain_hp -= int(damage_list[i])
    if remain_hp <0:
        remain_hp = 0
    return remain_hp

#現在の討伐状況から初期状態のボスhpを探してくる
def calc_default_hp(manage_dict,boss_arg_number,channel_id_str):
    boss_supress_number = manage_dict[channel_id_str]["boss_supress_number"]
    diff_number = boss_arg_number-1 - boss_supress_number%5
    if diff_number <0:
        diff_number +=5
    if boss_supress_number + diff_number <= 49:
        default_hp = boss_list_n[(boss_arg_number-1)%5].hp
    else:
        default_hp = boss_list_vh[(boss_arg_number-1)%5].hp
    return default_hp
    



def create_route_message(route):
    #text = "可能な３凸ルートの一覧です。参考にしてください\n------------------------------------------------------\n"
    text = f"{route[0][0]}: {route[0][1][0]} {route[0][1][1]} {route[0][1][2]} {route[0][1][3]} {route[0][1][4]} |{route[0][2]}"
    text += f"\n{route[1][0]}: {route[1][1][0]} {route[1][1][1]} {route[1][1][2]} {route[1][1][3]} {route[1][1][4]} |{route[1][2]}"
    text += f"\n{route[2][0]}: {route[2][1][0]} {route[2][1][1]} {route[2][1][2]} {route[2][1][3]} {route[2][1][4]} |{route[2][2]}"
    text += "\n------------------------------------------------------\n"
    return text

def list2tsv(a_list):
    #listをタブ区切り文字に置き換えるメソッド
    tsv = ""
    for a in a_list:
        if len(a) != 0:
            tsv += f"{a}\t"
    return tsv

def make_morning_message(guild,clan_dict):
    members = guild.get_role(clan_dict["role_id"]).members
    member_name_list=[member.display_name for member in members if not member.bot]

    dt_now = datetime.now(JST)
    date = dt_now.strftime("%m月%d日")

    task_kill_text = f"{date}のタスキル状況です。タスキルした場合には{sunglass}を送信してください"
    remain_totsu_text = f"{date}の凸状況です。凸が完了したらリアクションをしてください。"  
    for member_name in member_name_list:
        remain_totsu_text += f'\n3\t{member_name}\t'
        task_kill_text += f'\n{member_name}'

    return task_kill_text,remain_totsu_text   

# 起動時に動作する処理
@client.event
async def on_ready():
    # 起動したらターミナルにログイン通知が表示される
    print('ログインしました')

# メッセージ受信時に動作する処理
@client.event
async def on_message(message):
    # メッセージ送信者がBotだった場合は無視する
    if message.author.bot:
        return

    global manage_dict

    channel = message.channel
    author_display_name = message.author.display_name


    guild = client.get_guild(guild_id)
    channel_id_str = str(message.channel.id)

    argument_list = message.content.replace("　"," ").replace("   "," ").replace("  "," ").split(" ")

    #文末にスペースが入ってる場合には取り除く
    if len(argument_list[-1]) == 0:
        argument_list.pop(-1)

    if message.content.startswith("/battle") or message.content.startswith(".battle"):
        print(datetime.now(JST),author_display_name,message.guild.name,message.content,flush=True)
    
        if len(argument_list) == 1:        

            output_channel = guild.get_channel(manage_dict[channel_id_str]["output_channel"])

            #邪魔なので履歴を消去する
            async for old_message in output_channel.history(limit = 200):
                if old_message.author.id == minerva_id:
                    await old_message.delete()
                                

            manage_dict[channel_id_str]["boss_supress_number"] = 0

            #dictの初期化
            for i in range(5):
                manage_dict[channel_id_str]["reserve"][str(i)] = initialize_reserve(manage_dict[channel_id_str]["reserve"][str(i)],boss_list_n[i].hp)
            manage_dict[channel_id_str]["reserve"]["totsu"] = ""
            manage_dict[channel_id_str]["reserve"]["remain_hp"] = boss_list_n[0].hp

            bosyu_message = create_bosyu_message(0,manage_dict[channel_id_str]["reserve"])
            new_message = await output_channel.send(bosyu_message)
            
            manage_dict[channel_id_str]["message_id"] = new_message.id

            with open(json_file,"w") as f:
                json.dump(manage_dict,f)

            await message.add_reaction(ok_hand)
        
        #周回数およびボス番号を指定する，dictの初期化は行わない．
        if len(argument_list) == 3 and argument_list[1].isdecimal and argument_list[2].isdecimal:


            output_channel = guild.get_channel(manage_dict[channel_id_str]["output_channel"])

            #邪魔なので履歴を消去する
            async for old_message in output_channel.history(limit = 200):
                if old_message.author.id == minerva_id:
                    await old_message.delete()

            manage_dict[channel_id_str]["boss_supress_number"] = (int(argument_list[1])-1)*5 + int(argument_list[2])-1

            #dictの初期化
            for i in range(5):
                default_hp = calc_default_hp(manage_dict,int(argument_list[2])+i,channel_id_str)
                manage_dict[channel_id_str]["reserve"][str((int(argument_list[2])+i-1)%5)] = initialize_reserve(manage_dict[channel_id_str]["reserve"][str((int(argument_list[2])+i-1)%5)],default_hp)
            manage_dict[channel_id_str]["reserve"]["remain_hp"] = calc_default_hp(manage_dict,int(argument_list[2]),channel_id_str)
            manage_dict[channel_id_str]["reserve"]["totsu"] = ""

            bosyu_message = create_bosyu_message(manage_dict[channel_id_str]["boss_supress_number"],manage_dict[channel_id_str]["reserve"])
            new_message = await output_channel.send(bosyu_message)
            
            manage_dict[channel_id_str]["message_id"] = new_message.id

            with open(json_file,"w") as f:
                json.dump(manage_dict,f)

            await message.add_reaction(ok_hand)           

    if message.content.startswith("/reserve") or message.content.startswith(".reserve") or message.content.startswith("/rsv") or message.content.startswith(".rsv"):
        print(datetime.now(JST),author_display_name,message.guild.name,message.content,flush=True)
    
        if len(argument_list) == 3:
            if argument_list[1].isdecimal and argument_list[2].isdecimal:

                if int(argument_list[1]) > 5:
                    return await message.channel.send(f"{message.author.mention} 入力が不正です．ボス番号(`{argument_list[1]}`) は1から5までの整数である必要があります")

                remain_hp = manage_dict[channel_id_str]["reserve"][str(int(argument_list[1])-1)]["plan_remain_hp"]
                if remain_hp == 0:
                    if int(argument_list[1])-1 == manage_dict[channel_id_str]["boss_supress_number"]%5:
                        return await message.channel.send(f"{message.author.mention} 既に予約が埋まっています。予約者を無視する場合には `/totsu` コマンドを用いて下さい。")
                    else:
                        return await message.channel.send(f"{message.author.mention} 既に予約が埋まっています。")

                if int(argument_list[2]) >= 10000:
                    return await message.channel.send(f"{message.author.mention} ダメージ(`{argument_list[2]}`)は万単位で送信してください")

                if manage_dict[channel_id_str]["boss_supress_number"] %5 == int(argument_list[1]) -1:
                    default_hp = manage_dict[channel_id_str]["reserve"]["remain_hp"]
                else:
                    default_hp = calc_default_hp(manage_dict, int(argument_list[1]),channel_id_str)

                manage_dict[channel_id_str]["reserve"][str(int(argument_list[1])-1)]["members"] += f"{author_display_name}\t"
                manage_dict[channel_id_str]["reserve"][str(int(argument_list[1])-1)]["damages"] += f"{str(argument_list[2])}\t"
                manage_dict[channel_id_str]["reserve"][str(int(argument_list[1])-1)]["ids"] += f"{str(message.author.id)}\t"

                damage_list = manage_dict[channel_id_str]["reserve"][str(int(argument_list[1])-1)]["damages"].split("\t")
                
                manage_dict[channel_id_str]["reserve"][str(int(argument_list[1])-1)]["plan_remain_hp"] = calc_remain_hp(default_hp,damage_list) 

                new_message = create_bosyu_message(manage_dict[channel_id_str]["boss_supress_number"],
                                                manage_dict[channel_id_str]["reserve"])
    
                output_channel = guild.get_channel(manage_dict[channel_id_str]["output_channel"])
                bosyu_message = await output_channel.fetch_message(manage_dict[channel_id_str]["message_id"])
                await bosyu_message.edit(content=new_message)

                with open(json_file,"w") as f:
                    json.dump(manage_dict,f)

                await message.add_reaction(ok_hand)

            else:
                return await message.channel.send(f"{message.author.mention} 入力が不正です． ボス番号(`{argument_list[1]}`) 予定ダメージ(`{argument_list[2]}`)")

        elif len(argument_list) == 4: 
            if argument_list[1].isdecimal and argument_list[2].isdecimal and argument_list[3] == "mochi":

                if int(argument_list[2]) >= 10000:
                    return await message.channel.send(f"{message.author.mention} ダメージ(`{argument_list[2]}`)は万単位で送信してください")

                #remain_hp = manage_dict[channel_id_str]["reserve"][str(int(argument_list[1])-1)]["plan_remain_hp"]

                if manage_dict[channel_id_str]["boss_supress_number"] %5 == int(argument_list[1]) -1:
                    default_hp = manage_dict[channel_id_str]["reserve"]["remain_hp"]
                else:
                    default_hp = calc_default_hp(manage_dict, int(argument_list[1]),channel_id_str)

                manage_dict[channel_id_str]["reserve"][str(int(argument_list[1])-1)]["members"] = f"{author_display_name}\t"+manage_dict[channel_id_str]["reserve"][str(int(argument_list[1])-1)]["members"]
                manage_dict[channel_id_str]["reserve"][str(int(argument_list[1])-1)]["damages"] = f"{str(argument_list[2])}\t"+manage_dict[channel_id_str]["reserve"][str(int(argument_list[1])-1)]["damages"]
                manage_dict[channel_id_str]["reserve"][str(int(argument_list[1])-1)]["ids"] = f"{str(message.author.id)}\t"+manage_dict[channel_id_str]["reserve"][str(int(argument_list[1])-1)]["ids"]


                damage_list = manage_dict[channel_id_str]["reserve"][str(int(argument_list[1])-1)]["damages"].split("\t")
                
                manage_dict[channel_id_str]["reserve"][str(int(argument_list[1])-1)]["plan_remain_hp"] = calc_remain_hp(default_hp,damage_list) 
                manage_dict[channel_id_str]["reserve"][str(int(argument_list[1])-1)]["over"] = f"{author_display_name}\t"+manage_dict[channel_id_str]["reserve"][str(int(argument_list[1])-1)]["over"]
                
                new_message = create_bosyu_message(manage_dict[channel_id_str]["boss_supress_number"],
                                                manage_dict[channel_id_str]["reserve"])
    
                output_channel = guild.get_channel(manage_dict[channel_id_str]["output_channel"])
                bosyu_message = await output_channel.fetch_message(manage_dict[channel_id_str]["message_id"])
                await bosyu_message.edit(content=new_message)

                with open(json_file,"w") as f:
                    json.dump(manage_dict,f)
                await message.add_reaction(ok_hand)
        else:
            return await message.channel.send(f"{message.author.mention} 入力が不正です．`.reserve [ボス番号] [予定ダメージ]` を入力してください．\n持ち越しで凸予約する場合は`.reserve [ボス番号] [予定ダメージ] mochi` を入力してください．")


    if message.content.startswith("/cancel") or message.content.startswith(".cancel"):
        print(datetime.now(JST),author_display_name,message.guild.name,message.content,flush=True)
        if len(argument_list) == 1 :
            return await message.channel.send(f"{message.author.mention} ボス番号を入力してください")
        if argument_list[1].isdecimal:
            if int(argument_list[1]) > 5:
                return await message.channel.send(f"{message.author.mention} ボス番号`{argument_list[1]}`が不正です．1から5までの数字を送信してください")

            member_list = manage_dict[channel_id_str]["reserve"][str(int(argument_list[1])-1)]["members"].split("\t")
            if author_display_name in member_list:
                member_index = member_list.index(author_display_name)
                over_list = manage_dict[channel_id_str]["reserve"][str(int(argument_list[1])-1)]["over"].split("\t")
                damage_list = manage_dict[channel_id_str]["reserve"][str(int(argument_list[1])-1)]["damages"].split("\t")
                ids_list = manage_dict[channel_id_str]["reserve"][str(int(argument_list[1])-1)]["ids"].split("\t")
                
                manage_dict[channel_id_str]["reserve"]["totsu"] = manage_dict[channel_id_str]["reserve"]["totsu"].replace(f"{author_display_name}\t","") 

                
                member_list.pop(member_index)
                damage_list.pop(member_index)
                ids_list.pop(member_index)
                if member_index < len(over_list)-1:
                    over_list.pop(member_index)
                
                if manage_dict[channel_id_str]["boss_supress_number"] %5 == int(argument_list[1]) -1:
                    default_hp = manage_dict[channel_id_str]["reserve"]["remain_hp"]
                else:
                    default_hp = calc_default_hp(manage_dict, int(argument_list[1]),channel_id_str)

                manage_dict[channel_id_str]["reserve"][str(int(argument_list[1])-1)]["members"] = list2tsv(member_list)
                manage_dict[channel_id_str]["reserve"][str(int(argument_list[1])-1)]["damages"] = list2tsv(damage_list)
                manage_dict[channel_id_str]["reserve"][str(int(argument_list[1])-1)]["ids"] = list2tsv(ids_list)



                manage_dict[channel_id_str]["reserve"][str(int(argument_list[1])-1)]["plan_remain_hp"] = calc_remain_hp(default_hp,damage_list) 
                manage_dict[channel_id_str]["reserve"][str(int(argument_list[1])-1)]["over"] = list2tsv(over_list)
                
                new_message = create_bosyu_message(manage_dict[channel_id_str]["boss_supress_number"],
                                                manage_dict[channel_id_str]["reserve"])                
                output_channel = guild.get_channel(manage_dict[channel_id_str]["output_channel"])
                bosyu_message = await output_channel.fetch_message(manage_dict[channel_id_str]["message_id"])
                await bosyu_message.edit(content=new_message)

                with open(json_file,"w") as f:
                    json.dump(manage_dict,f)
                await message.add_reaction(ok_hand)
        else:
            return await message.channel.send(f"{message.author.mention} ボス番号`{argument_list[1]}`が不正です．1から5までの数字を送信してください")

    if message.content.startswith("/totsu") or message.content.startswith(".totsu"):
        print(datetime.now(JST),author_display_name,message.guild.name,message.content,flush=True)

        boss_now = str(manage_dict[channel_id_str]["boss_supress_number"]%5)
    
        if len(argument_list) == 1:
            member_list = manage_dict[channel_id_str]["reserve"][boss_now]["members"].split("\t")

            if author_display_name in member_list:
                manage_dict[channel_id_str]["reserve"]["totsu"] += f"{author_display_name}\t"
                
                new_message = create_bosyu_message(manage_dict[channel_id_str]["boss_supress_number"],
                                                manage_dict[channel_id_str]["reserve"])                
                output_channel = guild.get_channel(manage_dict[channel_id_str]["output_channel"])
                bosyu_message = await output_channel.fetch_message(manage_dict[channel_id_str]["message_id"])
                await bosyu_message.edit(content=new_message)

                with open(json_file,"w") as f:
                    json.dump(manage_dict,f)
                await message.add_reaction(ok_hand)


        elif len(argument_list) == 2:
            if argument_list[1].isdecimal:
                if author_display_name in manage_dict[channel_id_str]["reserve"][boss_now]["members"].split("\t"):
                    return await message.channel.send(f"{message.author.mention} 既に予約済みです．凸前宣言は`.totsu` を送信してください．\n持ち越しを消化する場合には`.totsu [予定ダメージ] mochi` を送信してください.")

                if int(argument_list[1]) >= 10000:
                    return await message.channel.send(f"{message.author.mention} ダメージ(`{argument_list[1]}`)は万単位で送信してください")

 
                default_hp = manage_dict[channel_id_str]["reserve"]["remain_hp"]
                manage_dict[channel_id_str]["reserve"][boss_now]["members"] += f"{author_display_name}\t"
                manage_dict[channel_id_str]["reserve"][boss_now]["damages"] += f"{str(argument_list[1])}\t"
                manage_dict[channel_id_str]["reserve"][boss_now]["ids"] += f"{str(message.author.id)}\t"
                manage_dict[channel_id_str]["reserve"]["totsu"] += f"{author_display_name}\t"

                damage_list = manage_dict[channel_id_str]["reserve"][boss_now]["damages"].split("\t")
                
                manage_dict[channel_id_str]["reserve"][boss_now]["plan_remain_hp"] = calc_remain_hp(default_hp,damage_list) 

                new_message = create_bosyu_message(manage_dict[channel_id_str]["boss_supress_number"],
                                                manage_dict[channel_id_str]["reserve"])

                output_channel = guild.get_channel(manage_dict[channel_id_str]["output_channel"])
                bosyu_message = await output_channel.fetch_message(manage_dict[channel_id_str]["message_id"])
                await bosyu_message.edit(content=new_message)

                with open(json_file,"w") as f:
                    json.dump(manage_dict,f)
                await message.add_reaction(ok_hand)
            else:
                return await message.channel.send(f"{message.author.mention} 入力が不正です．予定ダメージ(`{argument_list[1]}`)")


        elif len(argument_list) == 3 and argument_list[1].isdecimal:
            if argument_list[2] == "mochi":

                default_hp = manage_dict[channel_id_str]["reserve"]["remain_hp"]

                manage_dict[channel_id_str]["reserve"][boss_now]["members"] = f"{author_display_name}\t"+manage_dict[channel_id_str]["reserve"][boss_now]["members"]
                manage_dict[channel_id_str]["reserve"][boss_now]["damages"] = f"{str(argument_list[1])}\t"+manage_dict[channel_id_str]["reserve"][boss_now]["damages"]
                manage_dict[channel_id_str]["reserve"][boss_now]["ids"] = f"{str(message.author.id)}\t"+manage_dict[channel_id_str]["reserve"][boss_now]["ids"]
                manage_dict[channel_id_str]["reserve"]["totsu"] += f"{author_display_name}\t"


                damage_list = manage_dict[channel_id_str]["reserve"][boss_now]["damages"].split("\t")
                
                manage_dict[channel_id_str]["reserve"][boss_now]["plan_remain_hp"] = calc_remain_hp(default_hp,damage_list) 
                manage_dict[channel_id_str]["reserve"][boss_now]["over"] = f"{author_display_name}\t"+manage_dict[channel_id_str]["reserve"][boss_now]["over"]
                
                new_message = create_bosyu_message(manage_dict[channel_id_str]["boss_supress_number"],
                                                manage_dict[channel_id_str]["reserve"])
    
                output_channel = guild.get_channel(manage_dict[channel_id_str]["output_channel"])
                bosyu_message = await output_channel.fetch_message(manage_dict[channel_id_str]["message_id"])
                await bosyu_message.edit(content=new_message)

                with open(json_file,"w") as f:
                    json.dump(manage_dict,f)
                await message.add_reaction(ok_hand)
        else:
            return await message.channel.send(f"{message.author.mention} 入力が不正です．予定ダメージ(`{argument_list[1]}`)")


    if message.content.startswith("/fin") or message.content.startswith(".fin"):
        print(datetime.now(JST),author_display_name,message.guild.name,message.content,flush=True)

        if len(argument_list)==2 :
            argument_list[1] = argument_list[1].replace(",","")
            if not argument_list[1].isdecimal():
                return await message.channel.send(f"{message.author.mention} 入力が不正です．ダメージ(`{argument_list[1]}`)")

            if int(argument_list[1]) >= 10000:
                return await message.channel.send(f"{message.author.mention} ダメージ(`{argument_list[1]}`)は万単位で送信してください")
       
            totsu_list = manage_dict[channel_id_str]["reserve"]["totsu"].split("\t")
            boss_now = str(manage_dict[channel_id_str]["boss_supress_number"]%5)

            member_list = manage_dict[channel_id_str]["reserve"][boss_now]["members"].split("\t")       

            if not author_display_name in member_list:            
                text = f"{message.author.mention} 予約及び凸宣言がされていません"
                return await message.channel.send(content = text)
            #凸宣言してなければ無視
            if not author_display_name in totsu_list:
                text = f"{message.author.mention} 先に凸宣言を行ってください"
                return await message.channel.send(content = text)


            if argument_list[1].isdecimal:
                remain_hp = manage_dict[channel_id_str]["reserve"]["remain_hp"]
                remain_hp -= int(argument_list[1])
                manage_dict[channel_id_str]["reserve"]["remain_hp"] = remain_hp

                if remain_hp<=0:
                    text = message.author.mention + "ボスを討伐した場合は `/la [持ち越し時間]` を送信してください．"
                    return await channel.send(content=text)
                
                member_list = manage_dict[channel_id_str]["reserve"][boss_now]["members"].split("\t")
                member_index = member_list.index(author_display_name)
                over_list = manage_dict[channel_id_str]["reserve"][boss_now]["over"].split("\t")
                damage_list = manage_dict[channel_id_str]["reserve"][boss_now]["damages"].split("\t")
                #ids_list = manage_dict[channel_id_str]["reserve"][str(int(argument_list[1])-1)]["ids"].split("\t")

                
                member_list.pop(member_index)
                damage_list.pop(member_index)
                if member_index < len(over_list)-1:
                    over_list.pop(member_index)
                
                default_hp = remain_hp

                manage_dict[channel_id_str]["reserve"][boss_now]["members"] = list2tsv(member_list)
                manage_dict[channel_id_str]["reserve"][boss_now]["damages"] = list2tsv(damage_list)

                manage_dict[channel_id_str]["reserve"][boss_now]["plan_remain_hp"] = calc_remain_hp(default_hp,damage_list) 
                manage_dict[channel_id_str]["reserve"][boss_now]["over"] = list2tsv(over_list)
                manage_dict[channel_id_str]["reserve"]["totsu"] = manage_dict[channel_id_str]["reserve"]["totsu"].replace(f"{author_display_name}\t","")
                
                new_message = create_bosyu_message(manage_dict[channel_id_str]["boss_supress_number"],
                                                manage_dict[channel_id_str]["reserve"])                
                output_channel = guild.get_channel(manage_dict[channel_id_str]["output_channel"])
                bosyu_message = await output_channel.fetch_message(manage_dict[channel_id_str]["message_id"])
                await bosyu_message.edit(content=new_message)

                with open(json_file,"w") as f:
                    json.dump(manage_dict,f)

                #残凸管理しまーす
                remain_totsu_channel = guild.get_channel(manage_dict[channel_id_str]["remain_totsu_channel"])
                remain_totsu_message = await remain_totsu_channel.fetch_message(manage_dict[channel_id_str]["remain_totsu_message"])

                lines = remain_totsu_message.content.split("\n")
                new_lines = lines
                for i,line in enumerate(lines):
                    element_list = line.split("\t")
                    if i != 0:
                        if author_display_name == element_list[1]:
                            remain_totsu = int(element_list[0][0])
                            if remain_totsu != 0:
                                remain_totsu -=1
                                if len(element_list) == 3:
                                    new_lines[i] = f"{str(remain_totsu)}\t{author_display_name}\t{element_list[2]}"
                                else:
                                    new_lines[i] = f"{str(remain_totsu)}\t{author_display_name}"


                new_remain_totsu_message = ""
                for line in new_lines:
                    new_remain_totsu_message += f"{line}\n"
                
                await remain_totsu_message.edit(content=new_remain_totsu_message)

                #処理完了の挨拶
                await message.add_reaction(ok_hand)
        else:
            return message.channel.send(f"{message.author.mention} 入力が不正です．`.fin [与えたダメージ]` を送信してください．")



    #LA時用のコマンド
    if message.content.startswith("/la") or message.content.startswith(".la"):
        print(datetime.now(JST),author_display_name,message.guild.name,message.content,flush=True)
        totsu_list = manage_dict[channel_id_str]["reserve"]["totsu"].split("\t")
        boss_now = str(manage_dict[channel_id_str]["boss_supress_number"]%5)

        member_list = manage_dict[channel_id_str]["reserve"][boss_now]["members"].split("\t")

        if not author_display_name in member_list:            
            text = f"{message.author.mention} 予約及び凸宣言がされていません"
            return await message.channel.send(content = text)
        #凸宣言してなければ無視
        if not author_display_name in totsu_list:
            text = f"{message.author.mention} 先に凸宣言を行ってください"
            return await message.channel.send(content = text)
        boss_now = str(manage_dict[channel_id_str]["boss_supress_number"]%5)
    

        #残凸管理しまーす
        remain_totsu_channel = guild.get_channel(manage_dict[channel_id_str]["remain_totsu_channel"])
        remain_totsu_message = await remain_totsu_channel.fetch_message(manage_dict[channel_id_str]["remain_totsu_message"])

        lines = remain_totsu_message.content.split("\n")
        new_lines = lines
        for i,line in enumerate(lines):
            if i != 0:
                element_list = line.split("\t")
                if author_display_name == element_list[1]:
                    
                    if len(argument_list) == 1:
                        if len(element_list[0]) == 1:
                            message_content = f"{message.author.mention} 持ち越した場合には `/la [持ち越し時間]`を入力してください"
                            return await message.channel.send(content=message_content)

                        #持ち越しでLAを行った場合    
                        remain_totsu = int(element_list[0][0])
                        if remain_totsu != 0:
                            remain_totsu -=1
                            if len(element_list) == 3:
                                new_lines[i] = f"{str(remain_totsu)}\t{author_display_name}\t{element_list[2]}"
                            else:
                                new_lines[i] = f"{str(remain_totsu)}\t{author_display_name}"
   
                    else:
                        if len(element_list[0]) == 1:
                            #LAで持ち越した場合
                            boss_name = boss_list_n[int(boss_now)].name
                            remain_totsu = element_list[0]
                            if len(element_list) == 3:
                                new_lines[i] = f"{remain_totsu}(持ち越し:{boss_name} {argument_list[1]})\t{author_display_name}\t{element_list[2]}"
                            else:
                                new_lines[i] = f"{remain_totsu}(持ち越し:{boss_name} {argument_list[1]})\t{author_display_name}"                     
                        else:
                            #持ち越しでLAを行った場合 
                            message_content = f"{message.author.mention} 持ち越しの持ち越しは出来ません"
                            return await message.channel.send(content=message_content)

        new_remain_totsu_message = ""
        for line in new_lines:
            new_remain_totsu_message += f"{line}\n"
        
        await remain_totsu_message.edit(content=new_remain_totsu_message)

        #次のボス
        next_default_hp = calc_default_hp(manage_dict,(int(boss_now)+2)%5,channel_id_str)
        manage_dict[channel_id_str]["reserve"]["remain_hp"] = next_default_hp

        #次週の今倒したボスの初期化
        manage_dict[channel_id_str]["boss_supress_number"] += 1
        default_hp = calc_default_hp(manage_dict,(int(boss_now)+1)%5,channel_id_str)
        manage_dict[channel_id_str]["reserve"][boss_now] = initialize_reserve(manage_dict[channel_id_str]["reserve"][boss_now],default_hp)

        #凸状況の初期化
        manage_dict[channel_id_str]["reserve"]["totsu"] = ""


        new_message = create_bosyu_message(manage_dict[channel_id_str]["boss_supress_number"],
                                        manage_dict[channel_id_str]["reserve"])                
        output_channel = guild.get_channel(manage_dict[channel_id_str]["output_channel"])
        bosyu_message = await output_channel.fetch_message(manage_dict[channel_id_str]["message_id"])
        await bosyu_message.edit(content=new_message)



        notify_text = ""
        boss_next = str((int(boss_now)+1)%5)
        ids_list = manage_dict[channel_id_str]["reserve"][boss_next]["ids"].split("\t")
        for id in ids_list:
            if len(id) != 0:
                notify_member = guild.get_member(int(id))
                notify_text += f"{notify_member.mention}"
        if len(notify_text) != 0:
            notify_text += f"{boss_list_n[int(boss_next)].name}になりました。凸お願いします。"
            await channel.send(notify_text)
        await message.add_reaction(ok_hand)

    #残HPを調整する用のコマンド
    if message.content.startswith("/adjust") or message.content.startswith(".adjust"):
        print(datetime.now(JST),author_display_name,message.guild.name,message.content,flush=True)

        if len(argument_list)==2 :
            argument_list[1] = argument_list[1].replace(",","")

            if argument_list[1].isdecimal:


                if int(argument_list[1]) >= 10000:
                    return await message.channel.send(f"{message.author.mention} ボス残HP(`{argument_list[1]}`)は万単位で送信してください")        

                manage_dict[channel_id_str]["reserve"]["remain_hp"] = int(argument_list[1])
                boss_now = str(manage_dict[channel_id_str]["boss_supress_number"]%5)
                
                damage_list = manage_dict[channel_id_str]["reserve"][boss_now]["damages"].split("\t")
                default_hp = int(argument_list[1])
                manage_dict[channel_id_str]["reserve"][boss_now]["plan_remain_hp"] = calc_remain_hp(default_hp,damage_list) 
                
                new_message = create_bosyu_message(manage_dict[channel_id_str]["boss_supress_number"],
                                                manage_dict[channel_id_str]["reserve"])                
                output_channel = guild.get_channel(manage_dict[channel_id_str]["output_channel"])
                bosyu_message = await output_channel.fetch_message(manage_dict[channel_id_str]["message_id"])
                await bosyu_message.edit(content=new_message)

                with open(json_file,"w") as f:
                    json.dump(manage_dict,f)

                #処理完了の挨拶
                await message.add_reaction(ok_hand)            

                
        
    if message.content == "/ann" or message.content == ".ann":
        #zatsudan_channel = guild.get_channel(zatsudan_channel)
        serifu = "花火みたいでしょ？\n魔法って、こんな面白いことだって出来るんだよ。\nあなたがイメージすることなら、なんだって！"
        await message.channel.send(content=serifu,file=discord.File("./figs/ann.png"))
    
    #テロ,深夜の凸待ち中に打つなよ！絶対だぞ!!
    if message.content == "/terror" or message.content == ".terror":
        terror_list = glob.glob("./terror/*")
        await message.channel.send(file=discord.File(random.choice(terror_list)))

    if message.content == "/route" or message.content == ".route":
        gh = GspreadHandler()
        syoji_df = gh.dataset_fromSheet("育成済みリスト")
        form_df = gh.dataset_fromSheet("編成リスト")
        rc = RouteChecker(name=message.author.display_name,syoji_df=syoji_df,form_df=form_df)
        route_list = rc.find_route()
        for i,route in enumerate(route_list):
            await message.channel.send(content=create_route_message(route))
            print(i)

    #ユニ爺に0.7%の確率でうんこつける
#    if message.author.id == 435960125245620235:#ユニ爺うんち
 #       manage_dict["count"] += 1
#
 #       if manage_dict["count"] == 300:
  #          content = f"{message.author.mention}おめでとうございます．\nポイントが溜まりました!PUキャラが手に入りますよ!"
   #         await message.channel.send(content = content,file=discord.File("./figs/unchi_jii.jpg"))
    #        await message.add_reaction(unchi)
     #       manage_dict["count"] = 0
      #      
       # elif numpy.random.choice([False,True],p=[0.95,0.05]):
        #    serifu = f"{message.author.mention} おめでとうございます!"
         #   await message.channel.send(content = serifu,file=discord.File("./figs/karin.jpg"))
          #  await message.add_reaction(unchi)

       # with open(json_file,"w") as f:
        #    json.dump(manage_dict,f)        
        

        




@client.event
async def on_raw_reaction_add(payload):
    guild = client.get_guild(guild_id)
    
    channel = guild.get_channel(payload.channel_id)
    message_id = payload.message_id
    
    user_id = payload.user_id
    
    member = guild.get_member(user_id)
    member_display_name = member.display_name

    message = await channel.fetch_message(message_id)
    emoji = payload.emoji
    #ボットのつけるリアクションは無視する
    if member.bot:
        return

    emojis = guild.emojis
    magic_emoji_list = [emoji for emoji in emojis if "magic1"==emoji.name or "magic2"==emoji.name or "magic3" == emoji.name]
    attack_emoji_list = [emoji for emoji in emojis if "attack1"==emoji.name or "attack2"==emoji.name or "attack3" == emoji.name] 

    if "の凸状況です。凸が完了したらリアクションをしてください。" in message.content:
        if emoji in magic_emoji_list or emoji in attack_emoji_list:

            remain_totsu_kanri_message = message

            lines = remain_totsu_kanri_message.content.split("\n")
            new_lines = lines

            for i,line in enumerate(lines):
                if member_display_name in line:
                    if len(new_lines[i].split("\t")) == 3:
                        new_lines[i] += str(emoji)
                    else:
                        new_lines[i] += "\t"+str(emoji)

            
            new_text = ""

            for i,new_line in enumerate(new_lines):
                if i==0:
                    new_text += new_line
                else:
                    new_text += f"\n{new_line}"
            
            await remain_totsu_kanri_message.edit(content=new_text)
    
    
    if "タスキル状況です。タスキルした場合" in message.content:
        if payload.emoji.name == sunglass:
            lines = message.content.split("\n")
            new_line = lines
            for i,line in enumerate(lines):
                if line == member_display_name:
                    new_line[i] += sunglass
            
            new_text = ""
            for i,line in enumerate(new_line):
                if i==0:
                    new_text += line
                else:
                    new_text += f'\n{line}'
            
            await message.edit(content=new_text)

@client.event
async def on_member_join(member):
    guild = client.get_guild(guild_id)
    channel = guild.get_channel(zatsudan_channel_id)

    serifu = f"素敵な仲間が増えますよ!\n{member.mention}さん よろしくお願いしますね"

    await channel.send(content = serifu,file=discord.File("./figs/karin.jpg"))


@client.event
async def on_raw_reaction_remove(payload):
    guild = client.get_guild(guild_id)
    
    message_id = payload.message_id
    channel = guild.get_channel(payload.channel_id)

    user_id = payload.user_id

    emoji = payload.emoji

    
    member = guild.get_member(user_id)
    member_display_name = member.display_name
    message = await channel.fetch_message(message_id)
    
    if member.bot:
        return


    emojis = guild.emojis
    magic_emoji_list = [emoji for emoji in emojis if "magic1"==emoji.name or "magic2"==emoji.name or "magic3" == emoji.name]
    attack_emoji_list = [emoji for emoji in emojis if "attack1"==emoji.name or "attack2"==emoji.name or "attack3" == emoji.name] 

    if "の凸状況です。凸が完了したらリアクションをしてください。" in message.content:
        if emoji in magic_emoji_list or emoji in attack_emoji_list:

            remain_totsu_kanri_message = message

            lines = remain_totsu_kanri_message.content.split("\n")
            new_lines = lines
            for i,line in enumerate(lines):
                if member_display_name in line:
                    new_lines[i] = line.replace(str(emoji),"") 
            new_text = ""

            for i,new_line in enumerate(new_lines):
                if i==0:
                    new_text += new_line
                else:
                    new_text += f"\n{new_line}"
            
            await remain_totsu_kanri_message.edit(content=new_text)

    if "タスキル状況です。タスキルした場合" in message.content:
        if payload.emoji.name == sunglass:
            lines = message.content.split("\n")
            new_line = lines
            for i,line in enumerate(lines):
                if member_display_name in line :
                    new_line[i] =new_line[i].replace(sunglass,"")
            
            new_text = ""
            for i,line in enumerate(new_line):
                if i==0:
                    new_text += line
                else:
                    new_text += f'\n{line}'
            
            await message.edit(content=new_text)
 

 

# 60秒に一回ループ
@tasks.loop(seconds=60)
async def loop():
    # 現在の時刻
    now = datetime.now(JST).strftime('%H:%M')
    if now == '25:00': #クラバト期間中は朝5時に出すように書き換える
        guild = client.get_guild(guild_id)
        global manage_dict
        #デフォルトで絵文字をリアクションに付けておく
        emojis = guild.emojis
        magic_emoji_list = [emoji for emoji in emojis if "magic1"==emoji.name or "magic2"==emoji.name or "magic3" == emoji.name]
        attack_emoji_list = [emoji for emoji in emojis if "attack1"==emoji.name or "attack2"==emoji.name or "attack3" == emoji.name] 

        for clan_dict in clan_dicts:
            task_kill_text,remain_totsu_text  = make_morning_message(guild,clan_dict)

            remain_totsu_channnel = client.get_channel(clan_dict["remain_totsu_channel"])
        
            remain_totsu_kanri_message = await remain_totsu_channnel.send(content=remain_totsu_text)



            for emoji in attack_emoji_list:
                await remain_totsu_kanri_message.add_reaction(emoji)
            for emoji in magic_emoji_list:
                await remain_totsu_kanri_message.add_reaction(emoji)
            print("send zan totsu kanri message")
        

            manage_dict[str(clan_dict["command_channel"])]["remain_totsu_channel"] = clan_dict["remain_totsu_channel"]
            manage_dict[str(clan_dict["command_channel"])]["remain_totsu_message"] = remain_totsu_kanri_message.id

            with open(json_file,"w") as f:
                json.dump(manage_dict,f)        

            taskill_channel = client.get_channel(clan_dict["task_kill_channel"])
            taskill_message = await taskill_channel.send(content=task_kill_text)
            await taskill_message.add_reaction(sunglass)

    if now == '21:00':    
        guild = client.get_guild(guild_id)

        #歌劇団wikiのurl
        url = "https://wikiwiki.jp/yabaidesune/"

        #get html
        html = request.urlopen(url)
        soup = BeautifulSoup(html, "html.parser")
        ul_list = soup.find_all("ul", attrs={"class", "list1"})

        schedule_channel = guild.get_channel(schedule_channel_id)
        text = "** 開催中イベント情報 **"
        for i,ul in enumerate(ul_list):
            ul_text = ul.get_text()
            if "～" in ul_text:
            #if not "イベント一覧" in ul_text and ("イベント"in ul_text or "開催中キャンペーン" in ul_text or "クランバトル" in ul_text):
                text += f'\n\n{ul_text.replace("です☆","").replace("開催中","").replace("ですよ☆","").replace("☆","")}' 
        await schedule_channel.send(content=text)

#ループ処理実行
loop.start()
# Botの起動とDiscordサーバーへの接続
client.run(TOKEN)
