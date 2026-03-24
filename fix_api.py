import re

path = r"C:\Users\duskk\OneDrive - Strathmore University\Projects\NORT\apps\dashboard\app\lib\api.js"

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace getLeaderboard to accept mode param
content = content.replace(
    "export async function getLeaderboard(limit = 50) {\n  const res = await fetch(`${BASE}/api/leaderboard?limit=${limit}`);",
    "export async function getLeaderboard(limit = 50, mode = 'paper') {\n  const res = await fetch(`${BASE}/api/leaderboard?limit=${limit}&mode=${mode}`);"
)

# Replace getMyRank to accept mode param
content = content.replace(
    "export async function getMyRank(walletAddress) {\n  if (!walletAddress) return null;\n  // Always send lowercase — the DB stores wallet addresses lowercased\n  const addr = walletAddress.toLowerCase();\n  const res = await fetch(`${BASE}/api/leaderboard/me?wallet_address=${encodeURIComponent(addr)}`);",
    "export async function getMyRank(walletAddress, mode = 'paper') {\n  if (!walletAddress) return null;\n  const addr = walletAddress.toLowerCase();\n  const res = await fetch(`${BASE}/api/leaderboard/me?wallet_address=${encodeURIComponent(addr)}&mode=${mode}`);"
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Done")
