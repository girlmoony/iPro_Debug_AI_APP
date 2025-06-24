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

# shopコードとseat番号の抽出関数
def extract_shop_seat(filename):
    parts = filename.split('_')
    shop = parts[1]
    seat_full = parts[2]
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
