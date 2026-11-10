// Tiny adapter: sql.js Database -> { all(sql, params) } returning plain row objects.
export function wrapSqlJs(sqlDb) {
  return {
    all(sql, params = []) {
      const stmt = sqlDb.prepare(sql);
      try {
        stmt.bind(params);          // "?" placeholders filled in safely, never pasted into the SQL text
        const rows = [];
        while (stmt.step()) rows.push(stmt.getAsObject());
        return rows;
      } finally { stmt.free(); }
    },
  };
}
