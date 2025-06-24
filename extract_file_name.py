import pandas as pd
import json

# 判定結果シート読み込み（例）
excel_file = '判定結果まとめ.xlsx'
ipro_df = pd.read_excel(excel_file, sheet_name='判定結果')

# 属性情報のJSON
attr_json = {
    "1302@10": ["現行2", "旧型", "上", "左"],
    "1303@5": ["新型", "旧型", "下", "右"]
    # 必要な情報を追加
}
# JSONファイルのパス
json_file = 'attribute_info.json'

# JSON読み込み
with open(json_file, 'r', encoding='utf-8') as f:
    attr_json = json.load(f)

# 確認
print(attr_json)


# shopコードとseat番号の抽出関数
def extract_shop_seat(filename):
    parts = filename.split('_')
    shop = parts[1]
    seat_full = parts[2]
    seat = seat_full.split('-')[1]
    return shop, seat

def extract_shop_seat(filename):
    parts = filename.split('_')  
    # parts[0]から']'の位置を探して、その後ろを取得
    bracket_idx = parts[0].find(']')
    shop = parts[0][bracket_idx + 1:]  # ]の次の文字以降がshopコード
    
    # parts[1]のハイフン区切りの後ろがseat番号
    seat_full = parts[1]
    seat = seat_full.split('-')[1]
    
    return shop, seat

# shopとseat列を追加
ipro_df['shop'] = ipro_df['画像名'].apply(lambda x: extract_shop_seat(x)[0])
ipro_df['seat'] = ipro_df['画像名'].apply(lambda x: extract_shop_seat(x)[1])

# 属性列の追加
def get_attributes(row):
    key = f"{row['shop']}@{row['seat']}"
    return attr_json.get(key, ["不明", "不明", "不明", "不明"])

# 4つの属性列を分解して追加
ipro_df[['属性1', '属性2', '属性3', '属性4']] = ipro_df.apply(get_attributes, axis=1, result_type='expand')

# 結果確認
print(ipro_df[['画像名', 'shop', 'seat', '属性1', '属性2', '属性3', '属性4']].head())

# 必要なら新しいシートに保存
with pd.ExcelWriter(excel_file, mode='a', engine='openpyxl', if_sheet_exists='replace') as writer:
    ipro_df.to_excel(writer, sheet_name='判定結果_属性付加', index=False)

print('判定結果にshop, seat, 属性4列を追加し、新しいシートに保存しました。')

# 画像名の次に追加したい列
new_columns = ['shop', 'seat', '属性1', '属性2', '属性3', '属性4']

# 既存列のリスト取得
cols = list(ipro_df.columns)

# 画像名の位置を取得
img_idx = cols.index('画像名')

# 新しい列順序を作成
reordered_cols = cols[:img_idx + 1] + new_columns + [col for col in cols if col not in new_columns and col != '画像名']

# 列順序を並び替え
ipro_df = ipro_df[reordered_cols]

# 元シートを上書き（シート名は同じまま）
with pd.ExcelWriter(excel_file, mode='a', engine='openpyxl', if_sheet_exists='replace') as writer:
    ipro_df.to_excel(writer, sheet_name='判定結果', index=False)

print('元シートにshop, seat, 属性4列を画像名の次に追加し、上書き保存しました。')

