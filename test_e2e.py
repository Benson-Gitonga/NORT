import urllib.request, json

BASE = 'http://localhost:8000'
WALLET = '0xabc0000000000000000000000000000000000099'

def hit(method, path, body=None, label=None):
    url = BASE + path
    try:
        if body:
            data = json.dumps(body).encode()
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method=method)
        else:
            req = urllib.request.Request(url, method=method)
        with urllib.request.urlopen(req, timeout=8) as r:
            resp = json.loads(r.read())
            print('OK  [{}] {} {}'.format(r.status, method, label or path))
            return resp
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode()
        print('ERR [{}] {} {} -> {}'.format(e.code, method, label or path, body_txt[:140]))
        return None
    except Exception as e:
        print('ERR [---] {} {} -> {}'.format(method, label or path, e))
        return None

print('=== COLD START: wallet summary without prior connect ===')
r = hit('GET', '/api/wallet/summary?wallet_address=' + WALLET, label='wallet/summary cold')
if r:
    print('    balance={} trades={}'.format(r.get('paper_balance'), r.get('total_trades')))

print()
print('=== PLACE A TRADE ===')
r = hit('POST', '/api/papertrade', {
    'telegram_user_id': WALLET,
    'market_id': 'test-btc-100k',
    'market_question': 'Will BTC hit 100k?',
    'outcome': 'YES',
    'shares': 10,
    'price_per_share': 0.65,
    'direction': 'BUY'
})
if r:
    print('    trade_id={} cost={}'.format(r.get('trade_id'), r.get('total_cost')))

print()
print('=== WALLET AFTER TRADE ===')
r = hit('GET', '/api/wallet/summary?wallet_address=' + WALLET, label='wallet/summary after trade')
if r:
    print('    balance={} trades={}'.format(r.get('paper_balance'), r.get('total_trades')))

print()
print('=== LEADERBOARD ===')
r = hit('GET', '/api/leaderboard?limit=5')
if r:
    for e in r.get('leaderboard', []):
        print('    #{} {} pv={} xp={} badge={}'.format(
            e['rank'], e['display_name'], e['portfolio_value'], e['xp'], e['badge']['emoji']))

print()
print('=== MY RANK ===')
r = hit('GET', '/api/leaderboard/me?wallet_address=' + WALLET)
if r:
    print('    rank=#{} xp={} badge={}'.format(r.get('rank'), r.get('xp'), r.get('badge', {}).get('label')))

print()
print('=== USER STATS ===')
r = hit('GET', '/api/user/stats?wallet_address=' + WALLET)
if r:
    print('    xp={} level={} streak={} progress={}%'.format(
        r.get('xp'), r.get('level'), r.get('streak'), r.get('xpProgress')))

print()
print('=== ACHIEVEMENTS ===')
r = hit('GET', '/api/user/achievements?wallet_address=' + WALLET)
if r:
    earned = [a for a in r.get('achievements', []) if a['earned']]
    locked = [a for a in r.get('achievements', []) if not a['earned']]
    print('    earned={}'.format([a['name'] for a in earned]))
    print('    locked count={}'.format(len(locked)))

print()
print('=== SIGNALS ===')
r = hit('GET', '/api/signals/?top=3')
if r:
    print('    {} signals returned'.format(r.get('count', 0)))

print()
print('=== MARKETS ===')
r = hit('GET', '/api/markets')
if r:
    print('    {} markets in cache'.format(r.get('count', 0)))

print()
print('=== COMMIT TRADE (testnet receipt) ===')
r = hit('POST', '/api/trade/commit', {'trade_id': 1})
if r:
    print('    tx_hash={}'.format(r.get('tx_hash', '')[:20] + '...'))

print()
print('Done.')
