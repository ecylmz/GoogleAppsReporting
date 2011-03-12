#!/usr/bin/python
#
# Copyright (C) 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License")
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""This module implements a client for the Google Apps Reporting API.

The Google Apps Reporting API allows domain administrators the ability to
query user behaviour and resource usage for a given time frame.

The Google Apps Reporting API reference document is at:

http://code.google.com/apis/apps/reporting/google_apps_reporting_api.html

  ReportRequest:   Encapsulates attribute of a Reporting API request.
  Error:           Base error class.
  ReportError:     Error while executing report.
  ConnectionError: Error during HTTPS connection to a URL.
  ReportRunner:    Contains the web service calls to run a report.
  main():          Run a report with command-line arguments.
"""

import getopt
import re
import sys
import time
import urllib
import urllib2


class ReportRequest:

  """This class encapsulates the attributes of a Reporting API request."""

  _REQUEST_TEMPLATE = ('<?xml version="1.0" encoding="UTF-8"?>\n'
      '<rest xmlns="google:accounts:rest:protocol"\n'
      '    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
      '  <type>%(type)s</type>\n'
      '  <token>%(token)s</token>\n'
      '  <domain>%(domain)s</domain>\n'
      '  <date>%(date)s</date>\n'
      '  <reportType>%(report_type)s</reportType>\n'
      '  <reportName>%(report_name)s</reportName>\n'
      '</rest>\n')

  def __init__(self):
    """Initializes the report request with default values."""

    self.type = 'Report'
    self.token = None
    self.domain = None
    self.date = None
    self.report_type = 'daily'
    self.report_name = None

  def ToXml(self):
    """Return the XML request for the Reporting API.

    Returns:
      Reporting API XML request string.
    """
    return ReportRequest._REQUEST_TEMPLATE % self.__dict__


class Error(Exception):

  """Base error class."""

  pass


class LoginError(Error):

  """Unable to log in to authentication service."""

  pass

class ReportError(Error):

  """Report execution error class."""

  _ERROR_TEMPLATE = ('Error executing report:\n'
                     '  status=%(status)s\n'
                     '  reason=%(reason)s\n'
                     '  extended_message=%(extended_message)s\n'
                     '  result=%(result)s\n'
                     '  type=%(type)s\n')
  _STATUS_PATTERN  = re.compile(r'status>(.*?)<', re.DOTALL)
  _REASON_PATTERN  = re.compile('reason>(.*?)<', re.DOTALL)
  _EXTENDED_MESSAGE_PATTERN  = re.compile('extendedMessage>(.*?)<', re.DOTALL)
  _RESULT_PATTERN  = re.compile('result>(.*?)<', re.DOTALL)
  _TYPE_PATTERN  = re.compile('type>(.*?)<', re.DOTALL)

  def __init__(self):
    """Construct a report execution error."""

    Error.__init__(self, 'Error executing report')
    self.status = None
    self.reason = None
    self.extended_message = None
    self.result = None
    self.type = None

  def FromXml(self, xml):
    """Unmarshall an error from a Reporting API XML rstring.

    Args:
      xml: Reporting API XML response string.
    """
    match = ReportError._STATUS_PATTERN.search(xml)
    if match is not None: self.status = match.group(1)
    match = ReportError._REASON_PATTERN.search(xml)
    if match is not None: self.reason = match.group(1)
    match = ReportError._EXTENDED_MESSAGE_PATTERN.search(xml)
    if match is not None: self.extended_message = match.group(1)
    match = ReportError._RESULT_PATTERN.search(xml)
    if match is not None: self.result = match.group(1)
    match = ReportError._TYPE_PATTERN.search(xml)
    if match is not None: self.type = match.group(1)

  def __str__(self):
    """Override normal string representation with one which includes all the
    attributes of a report error.
    """
    return ReportError._ERROR_TEMPLATE % self.__dict__


class ConnectionError(Error):

  """URL connection error class."""

  def __init__(self, url, message):
    """Initializes the Error with a connection specific error message."""

    Error.__init__(self, 'URL connection error:\n' + message +
                   '\nwhile attempting to connect to: ' + url)


class ReportRunner:

  """This class contains the logic to generate a report from the Reporting API
  web service.
  """

  _AUTH_URL = 'https://www.google.com/accounts/ClientLogin'
  _REPORTING_URL = ('https://www.google.com'
                    '/hosted/services/v1.0/reports/ReportingData')

  def __init__(self):
    """Construct an instance of the report runner."""

    self.admin_email = None
    self.admin_password = None
    self.domain = None
    self.token = None

  def GetAdminEmailDomain(self):
    """Get administrator email adress domain.

    Returns:
      The domain portion of the administrator email address.
      e.g. For admin@example.com returns example.com
    """
    if self.admin_email is not None:
      at_index = self.admin_email.rfind('@')
      if at_index >= 0:
        return self.admin_email[at_index+1:]
    return None

  def GetLatestReportDate(self):
    """Get the date of the latest available report.

    Reports for the current date are available after 12:00 PST8PDT the following
    day.  We calculate and return the date of the latest available report based
    on the current time.  The PyTZ library can be used to calculate this more
    accurately, however since it is not part of a standard python installation
    we use -0800 as an approximation for the PST8PDT timezone.

    Returns:
      Latest report date.
    """
    _HOURS = 60*60
    _DAYS = 24*_HOURS
    now = time.time()
    pst_time = time.gmtime(now - 8 * _HOURS)
    if pst_time[3] < 12:
      latest = time.gmtime(now - 8 * _HOURS - 2 * _DAYS)
    else:
      latest = time.gmtime(now - 8 * _HOURS - 1 * _DAYS)
    return '%04i-%02i-%02i' % (latest[0], latest[1], latest[2])

  def __PostUrl(self, url, data):
    """Post data to a URL.

    Args:
      url: URL to post to.
      data: data to post

    Raises:
      ConnectionError: When a connection error occurs or an HTTP response
        error code is returned.
    """
    try:
      return urllib2.urlopen(url, data).read()
    except urllib2.HTTPError, e:
      raise ConnectionError(ReportRunner._AUTH_URL,
                            'HTTP Response Code: %i' % e.code)
    except urllib2.URLError, e:
      raise ConnectionError(ReportRunner._AUTH_URL, e.reason)

  def Login(self):
    """Get an authorization token from the Auth URL web service.

    This authorization token is cached in the ReportRunner instance.  If a new
    token is needed, for example if the token is 24 hours old, then call this
    method again to get a new token.

    Raises:
      ConnectionError: When a connection error occurs and in particular
        when the credentials are incorrect.
      LoginError: When authentication service does not return a SID token.
    """
    auth_request = urllib.urlencode({
        'accountType': 'HOSTED',
        'Email':       self.admin_email,
        'Passwd':      self.admin_password})
    auth_response = self.__PostUrl(ReportRunner._AUTH_URL, auth_request)
    for line in auth_response.split('\n'):
      (name, value) = line.split('=', 2)
      if name == 'SID':
        self.token = value
        return
    raise LoginError('Unable to get SID token from ' + ReportRunner._AUTH_URL)

  def GetReportData(self, report_request):
    """Get the report data response from the Reporting API web service.

    Args:
      report_request: Reporting API request.

    Returns:
      Report data response as a string.
    """
    report_response = self.__PostUrl(ReportRunner._REPORTING_URL,
                                     report_request.ToXml())
    if report_response is not None and report_response.startswith('<?xml'):
      report_error = ReportError()
      report_error.FromXml(report_response)
      raise report_error
    return report_response

  def WriteReport(self, response, out_file_name=None):
    """Print the report response to either standard output or a file.

    Args:
      response: Report data response.
      out_file_name: Output file name (optional).
    """
    if out_file_name is None:
      print response,
    else:
      out_file = open(out_file_name, 'w')
      print >> out_file, response,
      out_file.close()

  def RunReport(self, report_name, report_date, out_file_name=None):
    """Run the named report for the given day and write to the output file.

    Args:
      report_name: Name of the report to run.
      report_date: Run the report for this day.
      out_file_name: Write the report data to this file (optional).
    """
    if self.token is None:
      self.Login()
    request = ReportRequest()
    request.token = self.token
    if self.domain is not None:
      request.domain = self.domain
    else:
      request.domain = self.GetAdminEmailDomain()
    if report_date is None:
      report_date = self.GetLatestReportDate()
    request.report_name = report_name
    request.date = report_date
    response = self.GetReportData(request)
    self.WriteReport(response, out_file_name)


def _Usage():
  USAGE = ('_Usage: reporting.py --email=<email> --password=<password> '
           '[ --domain=<domain> ] --report=<report name> '
           '[ --date=<YYYY-MM-DD> ] [ --out=<file name> ]')
  print USAGE


def main():
  """Construct report request from command-line arguments and run the report.
  """
  try:
    (opts, args) = getopt.getopt(sys.argv[1:], '', ['email=', 'password=',
                                 'domain=', 'report=', 'date=', 'out='])
  except getopt.GetoptError:
    _Usage()
    sys.exit(2)
  opts = dict(opts)
  report_runner = ReportRunner()
  report_runner.admin_email = opts.get('--email')
  report_runner.admin_password = opts.get('--password')
  report_runner.domain = opts.get('--domain')
  report_name = opts.get('--report')
  report_date = opts.get('--date')
  out_file_name = opts.get('--out')
  if (not report_runner.admin_email or not report_runner.admin_password or
      not report_name or (report_date is not None
      and not re.compile('\d{4}-\d{2}-\d{2}').match(report_date))):
    _Usage()
    sys.exit(2)
  report_runner.RunReport(report_name, report_date, out_file_name)


if __name__ == '__main__':
  main()
