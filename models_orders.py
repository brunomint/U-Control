"""Modelos de ordem de culto (agenda + ordens datadas), substituindo
orders.json/order_templates.json/section_templates.json. `Order.date` é a
string "YYYY-MM-DD" original (mesma chave que orders.json já usava),
preservada como PK — é referenciada em URLs (`/view/order/<date>`,
`/order/<date>`) e nos links que a agenda gera. O 2º, 3º... culto do
mesmo dia usa "YYYY-MM-DD-N" (ver orders_store.key_date/key_seq); o
SQLite não impõe o tamanho do VARCHAR, por isso String(10) continua.

`OrderItem.kind` usa os valores "link"/"bible"/"freetext" — não "song":
existem itens reais com {title,url} apontando pra páginas que não são
músicas (ex: /bible, /order/new), então "song" seria enganoso e um convite
a acrescentar uma FK errada pra Song no futuro.

louvor/midia ficam como colunas JSON (blobs de config pequenos, sem
necessidade de consulta por campo) — inclui uma inconsistência real e
pré-existente nos dados (midia.equipe ora string, ora lista), normalizada
na importação (Fase 5.5), não no schema."""
from extensions import db


class Order(db.Model):
    date = db.Column(db.String(10), primary_key=True)
    tipo = db.Column(db.String(200), nullable=True)
    dirigente = db.Column(db.String(200), nullable=True)
    pregador = db.Column(db.String(200), nullable=True)
    horario = db.Column(db.String(50), nullable=True)
    horario_culto = db.Column(db.String(50), nullable=True)
    tema = db.Column(db.String(500), nullable=True)
    louvor = db.Column(db.JSON, nullable=True)
    midia = db.Column(db.JSON, nullable=True)

    itens = db.relationship(
        'OrderItem', backref='order', order_by='OrderItem.position',
        cascade='all, delete-orphan',
    )
    eventos = db.relationship(
        'EventoItem', backref='order', order_by='EventoItem.position',
        cascade='all, delete-orphan',
    )


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_date = db.Column(db.String(10), db.ForeignKey('order.date'), nullable=False)
    position = db.Column(db.Integer, nullable=False)
    kind = db.Column(db.String(20), nullable=False)  # link | bible | freetext
    title = db.Column(db.String(300), nullable=True)
    url = db.Column(db.String(500), nullable=True)
    any_text = db.Column(db.String(500), nullable=True)
    is_bible = db.Column(db.Boolean, nullable=True, default=False)
    reference = db.Column(db.String(200), nullable=True)


class EventoItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_date = db.Column(db.String(10), db.ForeignKey('order.date'), nullable=False)
    position = db.Column(db.Integer, nullable=False)
    titulo = db.Column(db.String(300), nullable=True)
    hora = db.Column(db.String(50), nullable=True)
    responsavel = db.Column(db.String(200), nullable=True)
    obs = db.Column(db.String(500), nullable=True)


class OrderTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    items = db.Column(db.JSON, nullable=False)


class SectionTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    section = db.Column(db.String(50), nullable=False)  # louvor | midia | eventos
    name = db.Column(db.String(200), nullable=False)
    fields = db.Column(db.JSON, nullable=False)
