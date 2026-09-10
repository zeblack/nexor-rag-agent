-- Grafo de entidades/relações via Apache AGE
CREATE EXTENSION IF NOT EXISTS age;
LOAD 'age';
SET search_path = ag_catalog, "$user", public;

SELECT create_graph('rag_graph') WHERE NOT EXISTS (
    SELECT 1 FROM ag_graph WHERE name = 'rag_graph'
);
