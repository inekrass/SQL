USE idz2;

SELECT
    column,
    formatReadableSize(sum(column_data_compressed_bytes)) AS compressed,
    formatReadableSize(sum(column_data_uncompressed_bytes)) AS uncompressed,
    round(sum(column_data_uncompressed_bytes) / sum(column_data_compressed_bytes), 2) AS ratio
FROM system.parts_columns
WHERE database = 'idz2'
  AND table = 'orders_flat'
  AND active
GROUP BY column
ORDER BY sum(column_data_uncompressed_bytes) DESC;