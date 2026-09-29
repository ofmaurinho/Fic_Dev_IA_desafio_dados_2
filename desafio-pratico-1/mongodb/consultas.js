// Consultas MongoDB — comentários e avaliações (RF07)
//
// Execução (container do projeto). O arquivo deve ser passado como script, e não
// via redirecionamento "<", pois o modo interativo quebra os encadeamentos em
// várias linhas:
//   docker cp mongodb/consultas.js desafio_dados_mongo:/tmp/consultas.js
//   docker exec desafio_dados_mongo mongosh --quiet "mongodb://localhost:27017/desafio_dados" /tmp/consultas.js
//
// Com o mongosh instalado no host, o container está na porta 27018:
//   mongosh --quiet "mongodb://localhost:27018/desafio_dados" mongodb/consultas.js
//
// Os documentos são carregados por `python -m src.main` na coleção `comentarios`.
// Cada documento mantém usuario_id e conteudo_id e recebe titulo, tipo e categoria
// do catálogo para permitir consultas e agregações sem JOIN.

db = db.getSiblingDB("desafio_dados");

print("\n1. Inserir documento (em coleção de demonstração, para não alterar a carga)");
db.comentarios_demo.drop();
const inserido = db.comentarios_demo.insertOne({
    usuario_id: 104,
    conteudo_id: 28,
    avaliacao: 5,
    comentario: "Conteúdo introdutório, claro e objetivo.",
    tags: ["didático", "iniciante", "python"],
    data: "2026-08-20",
    titulo: "Conteúdo de demonstração",
    tipo: "Artigo",
    categoria: "Programação & Software"
});
printjson(inserido);
db.comentarios_demo.drop();

print("\n2. Comentários de determinado conteúdo (conteudo_id = 587)");
db.comentarios
    .find(
        { conteudo_id: 587 },
        { _id: 0, usuario_id: 1, avaliacao: 1, comentario: 1, data: 1 }
    )
    .sort({ data: -1 })
    .forEach(printjson);

print("\n3. Documentos por tag (tags contém 'lgpd')");
print("Total: " + db.comentarios.countDocuments({ tags: "lgpd" }));
db.comentarios
    .find(
        { tags: "lgpd" },
        { _id: 0, conteudo_id: 1, titulo: 1, tags: 1 }
    )
    .limit(5)
    .forEach(printjson);

print("\n4. Avaliações filtradas pela nota");
print("Nota 5: " + db.comentarios.countDocuments({ avaliacao: 5 }));
print("Nota entre 1 e 2: " + db.comentarios.countDocuments({ avaliacao: { $gte: 1, $lte: 2 } }));
db.comentarios
    .find(
        { avaliacao: { $lte: 2 } },
        { _id: 0, conteudo_id: 1, avaliacao: 1, comentario: 1 }
    )
    .limit(5)
    .forEach(printjson);

print("\n5. Quantidade de comentários e nota média por categoria");
db.comentarios
    .aggregate([
        {
            $group: {
                _id: "$categoria",
                total_comentarios: { $sum: 1 },
                avaliacao_media: { $avg: "$avaliacao" }
            }
        },
        { $sort: { total_comentarios: -1 } },
        {
            $project: {
                _id: 0,
                categoria: "$_id",
                total_comentarios: 1,
                avaliacao_media: { $round: ["$avaliacao_media", 2] }
            }
        }
    ])
    .forEach(printjson);

print("\n6. Tags mais frequentes");
db.comentarios
    .aggregate([
        { $unwind: "$tags" },
        { $group: { _id: "$tags", total: { $sum: 1 } } },
        { $sort: { total: -1 } },
        { $limit: 10 }
    ])
    .forEach(printjson);
