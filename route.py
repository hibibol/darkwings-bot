
# -*- coding: utf-8 -*-
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials



class GspreadHandler(object):
    """
        python から Google SpreadSheet を使うときの関数など集めたクラス
    """
    def __init__(self):
        self.json_file = 'pricone-cda894e1aa6a.json'
        self.scope = ['https://spreadsheets.google.com/feeds']
        self.gsfile = None
        self.sheet_id = "1Pg3u-JxSYLPxEEgvt1rHU21TcNBfPW0gpZYFLKt31_M"
        self.get_gsfile()


    def get_gsfile(self):
        """ 読み書きするスプレッドシートのインスタンスを取得 """
        credentials = ServiceAccountCredentials.from_json_keyfile_name(self.json_file, self.scope)
        client = gspread.authorize(credentials)
        self.gsfile = client.open_by_key(self.sheet_id)


    def dataset_fromSheet(self, read_sheet_name):
        """
            スプレッドシートの該当シートを読み込んで前処理を行う。出力は DataFrame 型。

            read_sheet_name: 読み込み元シート名
        """

        # データ読み込み
        raw_data_sheet = self.gsfile.worksheet(read_sheet_name)
        dataset = pd.DataFrame(raw_data_sheet.get_all_values())

        # 0行目を列名にする
        dataset.columns =  list(dataset.iloc[0])
        dataset = dataset.drop(0, axis=0)
        dataset = dataset.reset_index(drop=True)
        return dataset

class RouteChecker(object):
    #ルートを見たい人の名前、育成済みリストのdataframe,編成リストのdataframe
    def __init__(self,name,syoji_df,form_df):

        df = syoji_df.replace("TRUE",1).replace("FALSE",0)
        self.syoji_dict = dict(zip(df["名前"],df[name]))
        self.form_list = []
        for row in form_df.itertuples():
            form = []
            form.append(row[1])
            
            chara_list = []
            for i in range(2,7):
                chara_list.append(row[i])
            form.append(chara_list)
            form.append(int(row[7]))
            self.form_list.append(form)
       


    def judge_attack(self,chara_list):
        new_dict = {}
        for chara in chara_list:
            new_dict[chara] = self.syoji_dict[chara] -1
        rental_count = 0
        for chara in chara_list:
            if new_dict[chara] == -1:
                rental_count += 1
        if rental_count >1:
            return False
        else:
            return True
            
    #その2凸の組み合わせが可能かどうかをみる
    def judge_double_attack(self,chara_list1,chara_list2):
        
        new_dict = {}
        
        for chara in chara_list1:
            new_dict[chara] = self.syoji_dict[chara] -1
            
        for chara in chara_list2:
            if chara in new_dict.keys():
                new_dict[chara] -=1
            else:
                new_dict[chara] = self.syoji_dict[chara] -1
        
        rental_count = 0
        
        for key in new_dict.keys():
            if new_dict[key] <0:
                rental_count -= new_dict[key]
        
        if rental_count>2:
            return False
        else:
            return True

    def judge_triple_attack(self,chara_list1,chara_list2,chara_list3):
        new_dict={}
        for chara in chara_list1:
            new_dict[chara] = self.syoji_dict[chara] -1
            
        for chara in chara_list2:
            if chara in new_dict.keys():
                new_dict[chara] -=1
            else:
                new_dict[chara] = self.syoji_dict[chara] -1

                        
        for chara in chara_list3:
            if chara in new_dict.keys():
                new_dict[chara] -=1
            else:
                new_dict[chara] = self.syoji_dict[chara] -1

        rental_count = 0
        
        for key in new_dict.keys():
            if new_dict[key] <0:
                rental_count -= new_dict[key]
        
        if rental_count>3:
            return False
        else:
            return True

    def find_route(self):
        route_list = []
        for i in range(len(self.form_list)):
            for j in range(i+1,len(self.form_list)):
                for k in range(j+1,len(self.form_list)):

                    #その凸自体が可能かどうか見る
                    if self.judge_attack(self.form_list[i][1]) and self.judge_attack(self.form_list[j][1]) and self.judge_attack(self.form_list[k][1]):
                        #2凸の組み合わせが可能かどうかを見る
                        if self.judge_double_attack(self.form_list[i][1],self.form_list[j][1])\
                            and self.judge_double_attack(self.form_list[k][1],self.form_list[j][1])\
                            and self.judge_double_attack(self.form_list[k][1],self.form_list[i][1]):
                            #3凸の組み合わせが可能かどうかを見る
                            if self.judge_triple_attack(self.form_list[i][1],self.form_list[j][1],self.form_list[k][1]):
                                route_list.append([self.form_list[i],self.form_list[j],self.form_list[k]])
        return route_list
