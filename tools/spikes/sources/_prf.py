from pathlib import Path

PRF_ACCIDENTS_DIR = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "raw"
    / "brazil"
    / "PRF"
    / "accidents"
)

PRF_ACCIDENTS_BY_OCCURRENCE_DICTIONARY_SCHEMA = {
    "x-dictionary": "https://drive.google.com/file/d/11pXLw_0D0hHVS8fiC8cv2dPX39vpuOH1/view?usp=drive_link",
    "title": "PRF Accidents by Occurrence Dictionary",
    "description": "Dictionary of accidents by occurrence.",
    "type": "object",
    "properties": {
        "id": {
            "type": "integer",
            "description": "Identifier of the accident.",
        },
        "data_inversa": {
            "type": "string",
            "description": "Date of the occurrence (YYYY-MM-DD).",
            "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$",
        },
        "dia_semana": {
            "type": "string",
            "description": "Day of the week of the occurrence in lowercase pt-BR locale (DDDD).",
            "enum": [
                "domingo",
                "segunda-feira",
                "terça-feira",
                "quarta-feira",
                "quinta-feira",
                "sexta-feira",
                "sábado",
            ],
        },
        "horario": {
            "type": "string",
            "description": "Time of the occurrence in 24-hour format (HH:MM:SS) on local time (UTC-3).",
            "pattern": "^[0-9]{2}:[0-9]{2}:[0-9]{2}$",
        },
        "uf": {
            "type": "string",
            "description": "Acronym of the State of the occurrence in uppercase (2 letters).",
            "pattern": "^[A-Z]{2}$",
        },
        "br": {
            "type": "integer",
            "description": "Identifier of Brazil's federal highway network of the occurrence.",
        },
        "km": {
            "type": "number",
            "description": "Kilometer of the occurrence in the federal highway network (BR).",
            "minimum": 0.1,
        },
        "municipio": {
            "type": "string",
            "description": "Denormalized uppercased name of the municipality of the occurrence in pt-BR.",
            "pattern": "^[A-Z\\s]+$",
        },
        "causa_acidente": {
            "type": "string",
            "description": "Cause of the accident in pt-BR.",
        },
        "tipo_acidente": {
            "type": "string",
            "description": "Type of the accident in pt-BR (e.g. Colisão frontal, Saída de pista, etc).",
        },
        "classificacao_acidente": {
            "type": ["string", "null"],
            "description": "Classification of the accident in pt-BR.",
            "enum": [
                "Sem Vítimas",
                "Com Vítimas Feridas",
                "Com Vítimas Fatais",
                "Ignorado",
                "NA",
            ],
        },
        "fase_dia": {
            "type": "string",
            "description": "Phase of the day in pt-BR (e.g. Amanhecer, Pleno dia, etc).",
        },
        "sentido_via": {
            "type": "string",
            "description": "Direction of the road in pt-BR.",
            "enum": ["Crescente", "Decrescente"],
        },
        "condicao_metereologica": {
            "type": "string",
            "description": "Weather condition in pt-BR (e.g. Céu claro, chuva, vento, etc).",
        },
        "tipo_pista": {
            "type": "string",
            "description": "Type of the road in pt-BR.",
            "enum": ["Dupla", "Simples", "Múltipla"],
        },
        "tracado_via": {
            "type": "string",
            "description": "Direction of the trace of the road in pt-BR.",
        },
        "uso_solo": {
            "type": "string",
            "description": "Characterization of the soil in pt-BR. Yes (Urban) or No (Rural).",
            "enum": ["Sim", "Não"],
        },
        "pessoas": {
            "type": "integer",
            "description": "Number of people involved in the accident.",
            "minimum": 0,
        },
        "mortos": {
            "type": "integer",
            "description": "Number of people killed in the accident.",
            "minimum": 0,
        },
        "feridos_leves": {
            "type": "integer",
            "description": "Number of people with light injuries in the accident.",
            "minimum": 0,
        },
        "feridos_graves": {
            "type": "integer",
            "description": "Number of people with serious injuries in the accident.",
            "minimum": 0,
        },
        "ilesos": {
            "type": "integer",
            "description": "Number of unharmed people in the accident.",
            "minimum": 0,
        },
        "ignorados": {
            "type": "integer",
            "description": "Number of people whose status is unknown in the accident.",
            "minimum": 0,
        },
        "feridos": {
            "type": "integer",
            "description": "Total number of people with injuries in the accident (feridos_leves + feridos_graves).",
            "minimum": 0,
        },
        "veiculos": {
            "type": "integer",
            "description": "Total number of vehicles involved in the accident.",
            "minimum": 0,
        },
        "latitude": {
            "type": "number",
            "description": "Latitude of the occurrence in geodetic decimal.",
            "minimum": -90,
            "maximum": 90,
        },
        "longitude": {
            "type": "number",
            "description": "Longitude of the occurrence in geodetic decimal.",
            "minimum": -180,
            "maximum": 180,
        },
        "regional": {
            "type": "string",
            "description": "Superintendence responsible for the boundaries where the occurrence took place, in uppercase.",
            "minLength": 7,
            "maxLength": 7,
            "pattern": "^SPRF-[A-Z]{2}$",
        },
        "delegacia": {
            "type": "string",
            "description": "Delegacy responsible for the boundaries where the occurrence took place, in uppercase.",
            "minLength": 8,
            "maxLength": 8,
            "pattern": "^DEL[0-9]{2}-[A-Z]{2}$",
        },
        "uop": {
            "type": "string",
            "description": "Police Operation Unit responsible for the boundaries where the occurrence took place, in uppercase.",
            "minLength": 14,
            "maxLength": 14,
            "pattern": "^UOP[0-9]{2}-DEL[0-9]{2}-[A-Z]{2}$",
        },
    },
    "required": [
        "id",
        "data_inversa",
        "dia_semana",
        "horario",
        "uf",
        "br",
        "km",
        "municipio",
        "causa_acidente",
        "tipo_acidente",
        "classificacao_acidente",
        "fase_dia",
        "sentido_via",
        "condicao_metereologica",
        "tipo_pista",
        "tracado_via",
        "uso_solo",
        "pessoas",
        "mortos",
        "feridos_leves",
        "feridos_graves",
        "ilesos",
        "ignorados",
        "feridos",
        "veiculos",
        "latitude",
        "longitude",
        "regional",
        "delegacia",
        "uop",
    ],
    "additionalProperties": False,
}
