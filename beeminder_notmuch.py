#!/usr/bin/env python

from __future__ import unicode_literals
from contextlib import closing
from datetime import datetime, timedelta
from io import StringIO
from nose.tools import assert_raises_regexp, eq_
import argparse
import httplib
import json
import os
import random
import re
import socket
import subprocess
import sys
import urllib

NOTMUCH_EXE = '/usr/local/bin/notmuch'

PROG = 'beeminder_notmuch'
HOST = 'www.beeminder.com'
AUTH_FILE = os.path.join(os.environ['HOME'], '.beeminder.auth')
API_PREFIX = '/api/v1'
API_DATA = API_PREFIX + '/users/%s/goals/%s/datapoints.json'
COMMENT = 'submitted by %s on %s' % (PROG, socket.gethostname())
UNITS = {'count': 'message', 'age': 'day'}


def main(argv=sys.argv):
    deps = {'open': open, 'check_output': subprocess.check_output,
            'stdout': sys.stdout, 'http': httplib.HTTPSConnection}
    run(deps, args().parse_args(argv[1:]))

def run(deps, opts):
    require_auth(deps, opts)
    k = globals()['collect_' + opts.datum](deps, opts)
    if opts.dry_run:
        deps['stdout'].write(
            '%d %s%s\n' % (k, UNITS[opts.datum], '' if k==1 else 's'))
    else:
        post_datum(deps, opts, k)

def require_auth(deps, opts):
    if not (opts.username and opts.auth_token):
        try:
            with deps['open'](AUTH_FILE) as auth:
                j = json.load(auth)
                opts.username = j['username']
                opts.auth_token = j['auth_token']
        except IOError:
            raise SystemExit('cannot open %r; see README' % AUTH_FILE)

def collect_count(deps, opts):
    cmd = [NOTMUCH_EXE, 'count'] + opts.search
    return int(deps['check_output'](cmd))

def collect_age(deps, opts):
    cmd = [NOTMUCH_EXE, 'search', '--sort=oldest-first', '--limit=1',
           '--format=json'] + opts.search
    j = json.loads(deps['check_output'](cmd))
    if len(j) == 0:
        return 0
    else:
        ts = int(j[0]['timestamp'])
        dt = datetime.now() - datetime.fromtimestamp(ts)
        return dt.days

def post_datum(deps, opts, k):
    path = API_DATA % (opts.username, opts.goal)
    if opts.message is None:
        opts.message = COMMENT
    params = urllib.urlencode({'auth_token': opts.auth_token,
                                     'comment': opts.message,
                                     'value': k})
    h = deps['http'](HOST)
    h.request('POST', path+'?'+params)
    r = h.getresponse()
    if r.status // 100 != 2:
        deps['stdout'].write('error %d posting %s=%d: %s\n' %
                             (r.status, opts.goal, k, r.read()))

def args():
    ap = argparse.ArgumentParser(
        prog=PROG,
        description='Tell beeminder about your notmuch mail')
    ap.add_argument('-n', '--dry-run', action='store_true',
                    help='just collect data; do not post')
    ap.add_argument('-u', dest='username',
                    help='beeminder username (default from ~/.beeminder.auth)')
    ap.add_argument('-a', dest='auth_token',
                    help='beeminder authentication token (~/.beeminder.auth)')
    ap.add_argument('-m', dest='message',
                    help='message to post with your data')
    ap.add_argument('datum', choices=['count', 'age'],
                    help='datum to report to beeminder')
    ap.add_argument('goal', metavar='GOAL',
                    help='short name of your goal on beeminder')
    ap.add_argument('search', metavar='SEARCH-TERM', nargs='+',
                    help='notmuch search term')
    return ap


### TEST CODE

def test_args_ok():
    yield args_ok, 'age g1 tag:foo',   lambda o: eq_(o.datum, 'age')
    yield args_ok, 'age g1 x -n',      lambda o: eq_(o.dry_run, True)
    yield args_ok, 'age g1 x',         lambda o: eq_(o.dry_run, False)
    yield args_ok, 'count g1 tag:foo', lambda o: eq_(o.datum, 'count')
    yield args_ok, 'count g1 tag:foo', lambda o: eq_(o.goal, 'g1')
    yield args_ok, 'count g1 tag:foo', lambda o: eq_(o.search, ['tag:foo'])
    yield args_ok, 'count g1 x y',     lambda o: eq_(o.search, ['x','y'])
    yield args_ok, 'count g1 x y',     lambda o: eq_(o.search, ['x','y'])
    yield args_ok, 'count g1 x y',     lambda o: eq_(o.search, ['x','y'])

def args_ok(s, p):
    p(args().parse_args(s.split()))

class mock_handle(object):
    def __init__(self, content):
        self.content = content

    def read(self):
        return self.content

    def close(self):
        pass

class mock_http_connection(object):
    def __init__(self, host, status, regex=''):
        eq_(host, HOST)
        self.status = status
        self.regex = regex

    def request(self, method, path):
        eq_(method, 'POST')
        assert re.search(self.regex, path)

    def getresponse(self):
        return argparse.Namespace(status=self.status, read=lambda: '')

def mock_http(status, regex=''):
    return lambda host: mock_http_connection(host, status, regex)

def mock_open_content(content):
    return lambda f: closing(mock_handle(content))

def mock_open_ioerror(f):
    raise IOError('no such file or directory: %r' % f)

MOCK_USER = 'al'
MOCK_TOKEN = 'alnet23845729'

def mock_opts(**kwargs):
    d = {'dry_run': False, 'username': None, 'auth_token': None,
         'message': None}
    d.update(kwargs)
    return argparse.Namespace(**d)

def mock_auth_opts(**kwargs):
    d = {'dry_run': False, 'username': MOCK_USER, 'auth_token': MOCK_TOKEN,
         'message': None}
    d.update(kwargs)
    return argparse.Namespace(**d)

def mock_check_output(regex, result):
    def f(cmd, *args, **kwargs):
        assert re.search(regex, ' '.join(cmd))
        return result
    return f

def mock_deps(out_regex='', out_result='', http_status=200, **kwargs):
    d = {'open': mock_open_ioerror,
         'check_output': mock_check_output(out_regex, out_result),
         'http': mock_http(http_status),
         'stdout': StringIO()}
    d.update(kwargs)
    return d

def test_require_auth_file():
    j = {'username': MOCK_USER, 'auth_token': MOCK_TOKEN}
    deps = mock_deps(open = mock_open_content(json.dumps(j)))
    o = mock_opts()
    require_auth(deps, o)
    eq_(o.username, MOCK_USER)
    eq_(o.auth_token, MOCK_TOKEN)

def test_require_auth_opts():
    o = mock_auth_opts()
    require_auth({}, o)
    eq_(o.username, MOCK_USER)
    eq_(o.auth_token, MOCK_TOKEN)

def test_require_auth_not_found():
    with assert_raises_regexp(SystemExit, 'cannot open'):
        run(mock_deps(), mock_opts())

def test_run_count():
    o = mock_auth_opts(datum='count', search=['xy'], goal='g1')
    deps = mock_deps(out_regex='count xy', out_result='42\n')
    run(deps, o)

def test_run_count_404():
    o = mock_auth_opts(datum='count', search=['xy'], goal='g1')
    deps = mock_deps(out_result='42\n', http=mock_http(404, '42'))
    run(deps, o)

def test_collect_count():
    o = mock_opts(search=['xy'])
    deps = mock_deps(out_regex='count xy', out_result='42\n')
    k = collect_count(deps, o)
    eq_(k, 42)

def test_collect_age():
    o = mock_opts(search=['zz'])
    p = 'search.*oldest-first.*json.*zz'
    dt = timedelta(days=random.randrange(3,25),
                   seconds=random.randrange(20, 80000))
    t0 = datetime.now() - dt
    j = [{'timestamp': t0.strftime('%s')}]
    deps = mock_deps(out_regex=p, out_result=json.dumps(j))
    k = collect_age(deps, o)
    eq_(k, dt.days)

def test_collect_age_empty():
    o = mock_opts(search=['zi'])
    deps = mock_deps(out_result='[]\n')
    k = collect_age(deps, o)
    eq_(k, 0)

def test_run_dry():
    o = mock_auth_opts(datum='count', search=['xy'], dry_run=True)
    deps = mock_deps(out_regex='count xy', out_result='42\n')
    run(deps, o)
    eq_(deps['stdout'].getvalue(), '42 messages\n')

def test_run_dry_singular():
    o = mock_auth_opts(datum='count', search=['xy'], dry_run=True)
    deps = mock_deps(out_regex='count xy', out_result='1\n')
    run(deps, o)
    eq_(deps['stdout'].getvalue(), '1 message\n')

if __name__ == '__main__': main()
