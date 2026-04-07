import sys
sys.path.insert(0, '.')

f = open('diag.txt', 'w')
try:
    f.write('Step 1: sys.path set\n')
    f.flush()
    
    from config.settings import Neo4jConfig
    f.write('Step 2: Neo4jConfig imported\n')
    f.flush()
    
    from infrastructure.neo4j_client import Neo4jConnection
    f.write('Step 3: Neo4jClient imported\n')
    f.flush()
    
    c = Neo4jConnection(Neo4jConfig())
    f.write('Step 4: Connection created\n')
    f.flush()
    
    ok, n = c.test_connection()
    f.write(f'Step 5: test_connection ok={ok} n={n}\n')
    f.flush()
    
    if ok:
        from data_access.repositories import OverviewRepo
        f.write('Step 6: OverviewRepo imported\n')
        f.flush()
        
        r = OverviewRepo(c)
        df = r.get_top_active_fighters()
        f.write(f'Step 7: Query returned {len(df)} rows\n')
        if len(df) > 0:
            f.write(df.head(5).to_string())
        f.write('\n')
        f.flush()
        
        r2 = r.get_top_ko_artists()
        f.write(f'Step 8: KO query returned {len(r2)} rows\n')
        f.flush()
    
    c.close()
    f.write('Step 9: Connection closed\n')
    f.write('ALL DONE\n')
    f.flush()
    
except Exception as e:
    f.write(f'\nERROR: {type(e).__name__}: {e}\n')
    import traceback
    traceback.print_exc(file=f)
    f.flush()
finally:
    f.close()
