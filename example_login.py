from steam_qr_login import SteamQRAuthenticator

auth = SteamQRAuthenticator(timeout=15.0)

qr_session = auth.start_session_with_qr(device_friendly_name="Python QR login")
print("[INFO] Challenge URL:", qr_session.challenge_url)
print("[INFO] QR Image URL :", auth.build_qr_image_url(qr_session.challenge_url))

poll_result = auth.wait_for_completion(qr_session, timeout=300.0, verbose=True)

print("[RESULT] steamid       :", poll_result.get("steamid"))
print("[RESULT] account_name  :", poll_result.get("account_name"))
print("[RESULT] access_token  :", poll_result.get("access_token"))
print("[RESULT] refresh_token :", poll_result.get("refresh_token"))
print("[RESULT] had_remote_int:", poll_result.get("had_remote_interaction"))
