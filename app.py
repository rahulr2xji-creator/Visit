from flask import Flask, request, jsonify
import json
import binascii
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import aiohttp
import asyncio
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from google.protobuf.json_format import MessageToJson
import uid_generator_pb2
import like_count_pb2

app = Flask(__name__)

def load_tokens(region):
    try:
        if region == "IND":
            with open("token_ind.json", "r") as f:
                tokens = json.load(f)
        elif region in {"BR", "US", "SAC", "NA"}:
            with open("token_br.json", "r") as f:
                tokens = json.load(f)
        else:
            with open("token_bd.json", "r") as f:
                tokens = json.load(f)
        return tokens
    except:
        return None

def encrypt_message(plaintext):
    try:
        key = b'Yg&tc%DEuh6%Zc^8'
        iv = b'6oyZDr22E3ychjM%'
        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded_message = pad(plaintext, AES.block_size)
        encrypted_message = cipher.encrypt(padded_message)
        return binascii.hexlify(encrypted_message).decode('utf-8')
    except:
        return None

def create_protobuf(uid):
    try:
        message = uid_generator_pb2.uid_generator()
        message.saturn_ = int(uid)
        message.garena = 1
        return message.SerializeToString()
    except:
        return None

def enc(uid):
    protobuf_data = create_protobuf(uid)
    if protobuf_data is None:
        return None
    encrypted_uid = encrypt_message(protobuf_data)
    return encrypted_uid

async def make_request_async(encrypt, region, token, session):
    try:
        if region == "IND":
            url = "https://client.ind.freefiremobile.com/GetPlayerPersonalShow"
        elif region in {"BR", "US", "SAC", "NA"}:
            url = "https://client.us.freefiremobile.com/GetPlayerPersonalShow"
        else:
            url = "https://clientbp.ggblueshark.com/GetPlayerPersonalShow"

        edata = bytes.fromhex(encrypt)
        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded",
            'Expect': "100-continue",
            'X-Unity-Version': "2018.4.11f1",
            'X-GA': "v1 1",
            'ReleaseVersion': "OB53"
        }

        async with session.post(url, data=edata, headers=headers, ssl=False, timeout=5) as response:
            if response.status != 200:
                return None
            hex_data = await response.read()
            binary = bytes.fromhex(hex_data.hex())
            decode = decode_protobuf(binary)
            return decode
    except:
        return None

def decode_protobuf(binary):
    try:
        items = like_count_pb2.Info()
        items.ParseFromString(binary)
        return items
    except:
        return None

@app.route('/visit', methods=['GET'])
async def visit():
    target_uid = request.args.get("uid")
    region = request.args.get("region", "").upper()

    if not target_uid:
        return jsonify({"error": "Target UID required"}), 400

    try:
        # 🔥 STEP 1 — REAL PLAYER INFO (LEVEL + REGION)
        player_info = fetch_player_info(target_uid)
        level = player_info["Level"]

        # Agar user galat region de to auto detect ho jayega
        if player_info["Region"] != "NA":
            region = player_info["Region"]

        tokens = load_tokens(region)
        if tokens is None:
            raise Exception("Failed to load tokens.")

        encrypted_target_uid = enc(target_uid)
        if encrypted_target_uid is None:
            raise Exception("Encryption failed.")

        total_visits = len(tokens)
        success_count = 0
        failed_count = 0
        player_name = None
        player_uid = None

        # 🔥 STEP 2 — VISIT REQUESTS
        async with aiohttp.ClientSession() as session:
            tasks = [
                make_request_async(encrypted_target_uid, region, token['token'], session)
                for token in tokens
            ]
            results = await asyncio.gather(*tasks)

        # 🔥 STEP 3 — PLAYER NAME + UID (protobuf se)
        for info in results:
            if info is not None:
                if player_name is None:
                    jsone = MessageToJson(info)
                    data_info = json.loads(jsone)

                    acc = data_info.get("AccountInfo", {})
                    player_name = acc.get("PlayerNickname")
                    player_uid = int(acc.get("UID", 0))

                success_count += 1
            else:
                failed_count += 1

        # 🔥 FINAL RESPONSE
        summary = {
            "TotalVisits": total_visits,
            "SuccessfulVisits": success_count,
            "FailedVisits": failed_count,
            "PlayerNickname": player_name,
            "Level": level,   # ✅ REAL LEVEL
            "UID": player_uid,
            "OB53": "Active",
            "Credits": "JCD X GOST"
        }

        return jsonify(summary)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
