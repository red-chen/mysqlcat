#!/usr/bin/env python2.7
#-*- coding:utf-8 -*-
'''
A lightweight wrapper around MySQLdb.

Created on Aug 9, 2015

@author: redchen1255@gmail.com
'''

import logging
import time
import itertools

import MySQLdb
import MySQLdb.cursors

class Connection(object):

    def __init__(self, 
                 host, 
                 database, 
                 user=None, 
                 password=None,
                 max_idle_time=7*3600,
                 autocommit=True,
                 pool = None):
        
        self.host = host
        self.database = database
        self.max_idle_time = max_idle_time
        self.autocommit = autocommit
        self.pool = pool
        
        # sql_mode mysql的写入模式，支持ANSI,TRADITIONAL,STRICT_TRANS_TABLES
        # ANSI模式：宽松模式，对插入数据进行校验，如果不符合定义类型或长度，对数据类型调整或截断保存，报warning警告。
        # TRADITIONAL模式：严格模式，当向mysql数据库插入数据时，进行数据的严格校验，保证错误数据不能插入，报error错误。用于事物时，会进行事物的回滚。
        # STRICT_TRANS_TABLES模式：严格模式，进行数据的严格校验，错误数据不能插入，报error错误。
        args = dict(
                    use_unicode=True, 
                    charset="utf8",
                    db=database,
                    sql_mode="TRADITIONAL")
        
        args["user"] = user
        args["passwd"] = password
        
        # We accept a path to a MySQL socket file or a host(:port) string
        if "/" in host:
            args["unix_socket"] = host
        else:
            self.socket = None
            pair = host.split(":")
            if len(pair) == 2:
                args["host"] = pair[0]
                args["port"] = int(pair[1])
            else:
                args["host"] = host
                args["port"] = 3306
        
        self._db = None
        self._db_args = args
        self._last_use_time = time.time()
        try:
            self.reconnect()
        except Exception:
            logging.error("Cannot connect to MySQL on %s", self.host, exc_info=True)
    
    def _ensure_connected(self):
        # Mysql by default closes client connections that are idle for
        # 8 hours, but the client library does not report this fact until
        # you try to perform a query and it fails.  Protect against this
        # case by preemptively closing and reopening the connection
        # if it has been idle for too long (7 hours by default).
        if (self._db is None or
            (time.time() - self._last_use_time > self.max_idle_time)):
            self.reconnect()
        self._last_use_time = time.time()
        
    def _cursor(self):
        self._ensure_connected()
        return self._db.cursor()
    
    def __del__(self):
        self.close()

    def close(self):
        """Closes this database connection."""
        if getattr(self, "_db", None) is not None:
            self._db.close()
            self._db = None
            
    def reconnect(self):
        """Closes the existing database connection and re-opens it."""
        self.close()
        if self.pool != None:
            self._db = self.pool.connection()
            self._db.cursor().connection.autocommit(self.autocommit)
        else:
            self._db = MySQLdb.connect(**self._db_args)
            self._db.autocommit(self.autocommit)
            
    def begin(self):
        """显示的开启事务
        
        注意：
        1.在支持事务的引擎中，默认已经开启了一个事务，但是在和PoolDB组合使用时，为了不让Pool共享连接，
        这里需要显示的调用底层的begin()函数，详见PoolDB注释：
            '''
            Note that you need to explicitly start transactions by calling the
            begin() method. This ensures that the connection will not be shared
            with other threads, that the transparent reopening will be suspended
            until the end of the transaction, and that the connection will be rolled
            back before being given back to the connection pool.
           '''
        2.使用事务时，需要设置autocommit=False
        """
        self._db.begin()
        
    def commit(self):
        """提交事务

        注意：commit函数只在支持事务的引擎上才有实际的作用，如InnoDB，在不支持事务的引擎上该函数
        没有实际的作用。所以期望使用事务时，在创建表的时候应该显示指定支持事务的引擎，如：
            '''
            create table {TABLE_NAME} (
            id varchar(32),
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8
            '''
        """
        try:
            self._db.commit()
        except Exception,e:
            logging.error(str(e))
            self._db.rollback();
    
    def _execute(self, cursor, query, *parameters):
        try:
            return cursor.execute(query, *parameters)
        except MySQLdb.OperationalError:
            logging.error("Error connecting to MySQL on %s", self.host)
            self.close()
            raise
            
    def write(self, insert_sql, *parameters):
        """单行写入函数
        
        例子：写入一行数据 
        >> write('INSERT INTO mytable values(%s)', 1)
        
        Args: 
            insert_sql : 写入数据的SQL语句
            parameters : 对应SQL语句的参数

        Returns: 
            返回当前操作写入系统的条数
        """
        cursor = self._cursor()
        try:
            self._execute(cursor, insert_sql, *parameters)
            return cursor.rowcount
        finally:
            cursor.close()
            
    def batchwrite(self, insert_sql, *parameters):
        """批量写入函数
        
        例子：写入三行数据 
        >> batchwrite('INSERT INTO mytable values(%s)', [(1), (2), (3)])
        

        Args:
            insert_sql : 写入数据的SQL语句
            parameters : 对应SQL语句的参数

        Returns: 
            返回当前操作写入系统的条数
        """
        cursor = self._cursor()
        try:
            cursor.executemany(insert_sql, *parameters)
            return cursor.rowcount
        finally:
            cursor.close()

    def read(self, query_sql, *parameters):
        """读取函数

        注意：如果请求的数据比较多时，请使用下面的‘iterator’的读取数据

        Args:
            insert_sql : 写入数据的SQL语句
            parameters : 对应SQL语句的参数

        Returns:
            查询的行数组
        """
        cursor = self._cursor()
        try:
            self._execute(cursor, query_sql, *parameters)
            column_names = [d[0] for d in cursor.description]
            return [Row(itertools.izip(column_names, row)) for row in cursor]
        finally:
            cursor.close()

    def iterator(self, query_sql, *parameters):
        """迭代读取函数

        例子：读取全表
           '''
           for row in iterator('select * from mytable'):
               print row
           '''

        Args:
            insert_sql : 写入数据的SQL语句
            parameters : 对应SQL语句的参数

        Returns:
            查询的行数组
        """
        self._ensure_connected()
        cursor = MySQLdb.cursors.SSCursor(self._db)
        try:
            self._execute(cursor, query_sql, *parameters)
            column_names = [d[0] for d in cursor.description]
            for row in cursor:
                yield Row(zip(column_names, row))
        finally:
            cursor.close()

class Row(dict):
    """A dict that allows for object-like property access syntax."""
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)
