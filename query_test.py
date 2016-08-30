#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 Measurement Lab
#
# Licensed under the Apache License, Version 2.0 (the "License");
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

import datetime
import unittest
import pytz

import query

class QueryConditionalsTest(unittest.TestCase):

  def setUp(self):
    start_time = datetime.datetime(2014, 1, 1, tzinfo=pytz.utc)
    end_time = datetime.datetime(2014, 2, 1, tzinfo=pytz.utc)
    client_ip_blocks = [(5, 10), (35, 80)]
    self.conditional = query.QueryConditionals(start_time, end_time, client_ip_blocks)

    self.generate_expected_nonmetric_dict(start_time, end_time, client_ip_blocks)

  def datetime_to_seconds(self, dt):
    return int((dt - datetime.datetime(1970, 1, 1, tzinfo=pytz.utc)).total_seconds())

  def generate_expected_nonmetric_dict(self, start_time, end_time, client_ip_blocks):
    start_time_unix = self.datetime_to_seconds(start_time)
    end_time_unix = self.datetime_to_seconds(end_time)

    expected_client_ip_blocks_0 = (
      'PARSE_IP(web100_log_entry.connection_spec.remote_ip) BETWEEN '
      '{start_block} AND {end_block}').format(
          start_block=client_ip_blocks[0][0],
          end_block=client_ip_blocks[0][1])

    expected_client_ip_blocks_1 = (
      'PARSE_IP(web100_log_entry.connection_spec.remote_ip) BETWEEN '
      '{start_block} AND {end_block}').format(
          start_block=client_ip_blocks[1][0],
          end_block=client_ip_blocks[1][1])

    expected_complete_tcp = (
      '(web100_log_entry.snap.State = 1\n\t'
      '\tOR (web100_log_entry.snap.State >= 5\n\t'
      '\t\tAND web100_log_entry.snap.State <= 11))')

    expected_log_time = (
      '(web100_log_entry.log_time >= {start_time})'
      ' AND (web100_log_entry.log_time < {end_time})').format(
          start_time=start_time_unix, end_time=end_time_unix)

    self.expected_nonmetric_dict = {
      'complete_tcp' : expected_complete_tcp,
      'log_time' : expected_log_time,
      'client_ip_blocks' : [expected_client_ip_blocks_0, expected_client_ip_blocks_1]
    }

  def test_download_dictionary_has_expected_metric_conditions(self):
    expected_download = (
      'web100_log_entry.snap.CongSignals > 0'
      '\n\tAND web100_log_entry.snap.HCThruOctetsAcked >= 8192'
      '\n\tAND (web100_log_entry.snap.SndLimTimeRwin +\n\t'
        '\tweb100_log_entry.snap.SndLimTimeCwnd +\n\t'
        '\tweb100_log_entry.snap.SndLimTimeSnd) >= 9000000'
      '\n\tAND (web100_log_entry.snap.SndLimTimeRwin +\n\t'
        '\tweb100_log_entry.snap.SndLimTimeCwnd +\n\t'
        '\tweb100_log_entry.snap.SndLimTimeSnd) < 3600000000')

    expected_data_direction = 'connection_spec.data_direction = 1'
    cond_dict = self.conditional.get_conditional_dict('download')

    self.assertEqual(cond_dict['download'], expected_download)
    self.assertEqual(cond_dict['data_direction'], expected_data_direction)

  def test_upload_dictionary_has_expected_conditions(self):
    cond_dict = self.conditional.get_conditional_dict('upload')

    actual_keys = cond_dict.keys()
    actual_keys.sort()
    self.assertListEqual(actual_keys, ['client_ip_blocks', 'complete_tcp', 'data_direction', 'log_time', 'upload'])

    expected_upload = (
      'web100_log_entry.snap.HCThruOctetsReceived >= 8192'
      '\n\tAND web100_log_entry.snap.Duration >= 9000000'
      '\n\tAND web100_log_entry.snap.Duration < 3600000000')

    expected_data_direction = (
      'connection_spec.data_direction = 0'
      '\n\tAND connection_spec.data_direction IS NOT NULL')

    # For each key in the dictionary, make sure it has the same value
    self.assertEqual(cond_dict['client_ip_blocks'], self.expected_nonmetric_dict['client_ip_blocks'])
    self.assertEqual(cond_dict['complete_tcp'], self.expected_nonmetric_dict['complete_tcp'])
    self.assertEqual(cond_dict['log_time'], self.expected_nonmetric_dict['log_time'])

    self.assertEqual(cond_dict['upload'], expected_upload)
    self.assertEqual(cond_dict['data_direction'], expected_data_direction)

  def test_minimum_rtt_dictionary_has_expected_metric_conditions(self):
    expected_minimum_rtt = (
      'web100_log_entry.snap.CongSignals > 0'
      '\n\tAND web100_log_entry.snap.HCThruOctetsAcked >= 8192'
      '\n\tAND (web100_log_entry.snap.SndLimTimeRwin +\n\t'
        '\tweb100_log_entry.snap.SndLimTimeCwnd +\n\t'
        '\tweb100_log_entry.snap.SndLimTimeSnd) >= 9000000'
      '\n\tAND (web100_log_entry.snap.SndLimTimeRwin +\n\t'
        '\tweb100_log_entry.snap.SndLimTimeCwnd +\n\t'
        '\tweb100_log_entry.snap.SndLimTimeSnd) < 3600000000'
      '\n\tAND web100_log_entry.snap.CountRTT > 10'
    )

    expected_data_direction = 'connection_spec.data_direction = 1'
    cond_dict = self.conditional.get_conditional_dict('minimum_rtt')
    self.assertEqual(cond_dict['minimum_rtt'], expected_minimum_rtt)
    self.assertEqual(cond_dict['data_direction'], expected_data_direction)

class SubQueryGeneratorTest(unittest.TestCase):

  def setUp(self):
    self.start_time = datetime.datetime(2014, 1, 1, tzinfo=pytz.utc)
    self.end_time = datetime.datetime(2014, 2, 1, tzinfo=pytz.utc)
    self.client_ip_blocks = [(5, 10), (35, 80)]

  def test_download_subquery_is_correct(self):
    subquery = query.SubQueryGenerator('download', self.start_time, self.end_time, self.client_ip_blocks)
    expected_query = (
      'SELECT\n\t'
      'web100_log_entry.log_time AS timestamp,\n\t'
      '8 * (web100_log_entry.snap.HCThruOctetsAcked /\n\t\t'
      '(web100_log_entry.snap.SndLimTimeRwin +\n\t\t'
      ' web100_log_entry.snap.SndLimTimeCwnd +\n\t\t'
      ' web100_log_entry.snap.SndLimTimeSnd)) AS download_mbps\n'
      'FROM\n\tplx.google:m_lab.ndt.all\n'
      'WHERE\n\t'
      'connection_spec.data_direction = 1'
      '\n\t AND '
        'web100_log_entry.snap.CongSignals > 0'
        '\n\tAND web100_log_entry.snap.HCThruOctetsAcked >= 8192'
        '\n\tAND (web100_log_entry.snap.SndLimTimeRwin +\n\t'
          '\tweb100_log_entry.snap.SndLimTimeCwnd +\n\t'
          '\tweb100_log_entry.snap.SndLimTimeSnd) >= 9000000'
        '\n\tAND (web100_log_entry.snap.SndLimTimeRwin +\n\t'
          '\tweb100_log_entry.snap.SndLimTimeCwnd +\n\t'
          '\tweb100_log_entry.snap.SndLimTimeSnd) < 3600000000'
      '\n\tAND '
        '(web100_log_entry.log_time >= 1388534400)'
        ' AND (web100_log_entry.log_time < 1391212800)'
      '\n\tAND ('
        'PARSE_IP(web100_log_entry.connection_spec.remote_ip) BETWEEN 5 AND 10 OR\n\t\t'
        'PARSE_IP(web100_log_entry.connection_spec.remote_ip) BETWEEN 35 AND 80)'
    )
    self.assertEqual(subquery.query, expected_query)

  def test_upload_subquery_is_correct(self):
    subquery = query.SubQueryGenerator('upload', self.start_time, self.end_time, self.client_ip_blocks)
    expected_query = (
      'SELECT\n\t'
      'web100_log_entry.log_time AS timestamp,\n\t'
      '8 * (web100_log_entry.snap.HCThruOctetsReceived /\n\t\t'
      ' web100_log_entry.snap.Duration) AS upload_mbps\n'
      'FROM\n\tplx.google:m_lab.ndt.all\n'
      'WHERE\n\t'
      'connection_spec.data_direction = 0'
        '\n\tAND connection_spec.data_direction IS NOT NULL'
      '\n\t AND '
        'web100_log_entry.snap.HCThruOctetsReceived >= 8192'
        '\n\tAND web100_log_entry.snap.Duration >= 9000000'
        '\n\tAND web100_log_entry.snap.Duration < 3600000000'
      '\n\tAND '
        '(web100_log_entry.log_time >= 1388534400)'
        ' AND (web100_log_entry.log_time < 1391212800)'
      '\n\tAND ('
        'PARSE_IP(web100_log_entry.connection_spec.remote_ip) BETWEEN 5 AND 10 OR\n\t\t'
        'PARSE_IP(web100_log_entry.connection_spec.remote_ip) BETWEEN 35 AND 80)'
      )

    self.assertEqual(subquery.query, expected_query)

  def test_rtt_subquery_is_correct(self):
    subquery = query.SubQueryGenerator('minimum_rtt', self.start_time, self.end_time, self.client_ip_blocks)
    expected_query = (
      'SELECT\n\t'
      'web100_log_entry.log_time AS timestamp,\n\t'
      'web100_log_entry.snap.MinRTT AS minimum_rtt_ms\n'
      'FROM\n\tplx.google:m_lab.ndt.all\n'
      'WHERE\n\t'
      'connection_spec.data_direction = 1'
      '\n\t AND web100_log_entry.snap.CongSignals > 0'
        '\n\tAND web100_log_entry.snap.HCThruOctetsAcked >= 8192'
        '\n\tAND (web100_log_entry.snap.SndLimTimeRwin +\n\t'
          '\tweb100_log_entry.snap.SndLimTimeCwnd +\n\t'
          '\tweb100_log_entry.snap.SndLimTimeSnd) >= 9000000'
        '\n\tAND (web100_log_entry.snap.SndLimTimeRwin +\n\t'
          '\tweb100_log_entry.snap.SndLimTimeCwnd +\n\t'
          '\tweb100_log_entry.snap.SndLimTimeSnd) < 3600000000'
          '\n\tAND web100_log_entry.snap.CountRTT > 10'
      '\n\tAND '
        '(web100_log_entry.log_time >= 1388534400)'
        ' AND (web100_log_entry.log_time < 1391212800)'
      '\n\tAND ('
        'PARSE_IP(web100_log_entry.connection_spec.remote_ip) BETWEEN 5 AND 10 OR\n\t\t'
        'PARSE_IP(web100_log_entry.connection_spec.remote_ip) BETWEEN 35 AND 80)'
    )
    self.assertEqual(subquery.query, expected_query)

  def test_subquery_with_mock_metric_raises_not_implemented_error(self):
    with self.assertRaises(NotImplementedError):
      query.SubQueryGenerator('mock_metric', self.start_time, self.end_time, self.client_ip_blocks)

class BuildMetricMedianQueryTest(unittest.TestCase):

  def setUp(self):
    self.start_time = datetime.datetime(2014, 1, 1, tzinfo=pytz.utc)
    self.end_time = datetime.datetime(2014, 2, 1, tzinfo=pytz.utc)
    self.client_ip_blocks = [(5, 10), (35, 80)]

  def test_build_valid_median_query(self):
    actual = query.build_metric_median_query(self.start_time, self.end_time, self.client_ip_blocks)
    expected_download_subquery = (
      'SELECT\n\t'
      'web100_log_entry.log_time AS timestamp,\n\t'
      '8 * (web100_log_entry.snap.HCThruOctetsAcked /\n\t\t'
      '(web100_log_entry.snap.SndLimTimeRwin +\n\t\t'
      ' web100_log_entry.snap.SndLimTimeCwnd +\n\t\t'
      ' web100_log_entry.snap.SndLimTimeSnd)) AS download_mbps\n'
      'FROM\n\tplx.google:m_lab.ndt.all\n'
      'WHERE\n\t'
      'connection_spec.data_direction = 1'
      '\n\t AND '
        'web100_log_entry.snap.CongSignals > 0'
        '\n\tAND web100_log_entry.snap.HCThruOctetsAcked >= 8192'
        '\n\tAND (web100_log_entry.snap.SndLimTimeRwin +\n\t'
          '\tweb100_log_entry.snap.SndLimTimeCwnd +\n\t'
          '\tweb100_log_entry.snap.SndLimTimeSnd) >= 9000000'
        '\n\tAND (web100_log_entry.snap.SndLimTimeRwin +\n\t'
          '\tweb100_log_entry.snap.SndLimTimeCwnd +\n\t'
          '\tweb100_log_entry.snap.SndLimTimeSnd) < 3600000000'
      '\n\tAND '
        '(web100_log_entry.log_time >= 1388534400)'
        ' AND (web100_log_entry.log_time < 1391212800)'
      '\n\tAND ('
        'PARSE_IP(web100_log_entry.connection_spec.remote_ip) BETWEEN 5 AND 10 OR\n\t\t'
        'PARSE_IP(web100_log_entry.connection_spec.remote_ip) BETWEEN 35 AND 80)'
    )
    expected_upload_subquery = (
      ',\n\t'
      'SELECT\n\t'
      'web100_log_entry.log_time AS timestamp,\n\t'
      '8 * (web100_log_entry.snap.HCThruOctetsReceived /\n\t\t'
      ' web100_log_entry.snap.Duration) AS upload_mbps\n'
      'FROM\n\tplx.google:m_lab.ndt.all\n'
      'WHERE\n\t'
      'connection_spec.data_direction = 0'
        '\n\tAND connection_spec.data_direction IS NOT NULL'
      '\n\t AND '
        'web100_log_entry.snap.HCThruOctetsReceived >= 8192'
        '\n\tAND web100_log_entry.snap.Duration >= 9000000'
        '\n\tAND web100_log_entry.snap.Duration < 3600000000'
      '\n\tAND '
        '(web100_log_entry.log_time >= 1388534400)'
        ' AND (web100_log_entry.log_time < 1391212800)'
      '\n\tAND ('
        'PARSE_IP(web100_log_entry.connection_spec.remote_ip) BETWEEN 5 AND 10 OR\n\t\t'
        'PARSE_IP(web100_log_entry.connection_spec.remote_ip) BETWEEN 35 AND 80)'
      )
    expected_rtt_subquery = (
      ',\n\t'
      'SELECT\n\t'
      'web100_log_entry.log_time AS timestamp,\n\t'
      'web100_log_entry.snap.MinRTT AS minimum_rtt_ms\n'
      'FROM\n\tplx.google:m_lab.ndt.all\n'
      'WHERE\n\t'
      'connection_spec.data_direction = 1'
      '\n\t AND web100_log_entry.snap.CongSignals > 0'
        '\n\tAND web100_log_entry.snap.HCThruOctetsAcked >= 8192'
        '\n\tAND (web100_log_entry.snap.SndLimTimeRwin +\n\t'
          '\tweb100_log_entry.snap.SndLimTimeCwnd +\n\t'
          '\tweb100_log_entry.snap.SndLimTimeSnd) >= 9000000'
        '\n\tAND (web100_log_entry.snap.SndLimTimeRwin +\n\t'
          '\tweb100_log_entry.snap.SndLimTimeCwnd +\n\t'
          '\tweb100_log_entry.snap.SndLimTimeSnd) < 3600000000'
          '\n\tAND web100_log_entry.snap.CountRTT > 10'
      '\n\tAND '
        '(web100_log_entry.log_time >= 1388534400)'
        ' AND (web100_log_entry.log_time < 1391212800)'
      '\n\tAND ('
        'PARSE_IP(web100_log_entry.connection_spec.remote_ip) BETWEEN 5 AND 10 OR\n\t\t'
        'PARSE_IP(web100_log_entry.connection_spec.remote_ip) BETWEEN 35 AND 80)'
    )

    expected = (
      'SELECT\n\t'
      'NTH( 51, QUANTILES(download, 101)) AS download_mbps,\n\t'
      'NTH( 51, QUANTILES(upload, 101)) AS upload_mbps,\n\t'
      'NTH( 51, QUANTILES(minimum_rtt, 101)) AS minimum_rtt_ms\n'
      'FROM\n\t'
      '{download}'
      '{upload}'
      '{min_rtt}'
      ).format(download=expected_download_subquery, upload=expected_upload_subquery, min_rtt=expected_rtt_subquery)

    self.assertEqual(expected, actual)


if __name__ == '__main__':
  unittest.main()
