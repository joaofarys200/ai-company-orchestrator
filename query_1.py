
import sqlite3

DB_FILE = "ecommerce.db"

def obter_conexao():
    return sqlite3.connect(DB_FILE)

def query_total_gasto_por_utilizador():
    conn = obter_conexao()
    cursor = conn.cursor()
    
    query = """
        SELECT
            u.nome AS NomeUtilizador,
            SUM(c.quantidade * p.preco) AS TotalGasto
        FROM
            utilizadores u
        INNER JOIN
            compras c ON u.id = c.utilizador_id
        INNER JOIN
            produtos p ON c.produto_id = p.id
        GROUP BY
            u.nome
        ORDER BY
            TotalGasto DESC;
    """
    
    cursor.execute(query)
    resultados = cursor.fetchall()
    conn.close()
    
    print("\n--- Total Gasto por Utilizador ---")
    for linha in resultados:
        print(f"Utilizador: {linha[0]}, Total Gasto: {linha[1]:.2f}€")
    return resultados

if __name__ == "__main__":
    query_total_gasto_por_utilizador()
