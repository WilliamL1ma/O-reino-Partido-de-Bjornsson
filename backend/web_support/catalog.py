RACES = [
    {
        "slug": "humano",
        "name": "Humano",
        "summary": "Versáteis e adaptáveis, com grande facilidade para aprender e se ajustar a qualquer papel.",
        "traits": [
            "Versatilidade: pode escolher uma habilidade adicional no nível 1.",
            "Ambição Humana: +1 em dois atributos de sua escolha.",
            "Liderança: bônus em interações sociais.",
        ],
    },
    {
        "slug": "anao",
        "name": "Anão",
        "summary": "Pequenos, robustos e resistentes, ligados à forja, à terra e à disciplina ancestral.",
        "traits": [
            "Resistência Anã: vantagem contra veneno e algumas magias.",
            "Mestre Ferreiro: afinidade com forja e criação de equipamentos.",
            "Resistência: +2 em Constituição.",
        ],
    },
    {
        "slug": "elfo",
        "name": "Elfo",
        "summary": "Graciosos, longevos e naturalmente ligados à magia, à natureza e à percepção.",
        "traits": [
            "Visão Aguçada: percepção ampliada e visão noturna.",
            "Magia Natural: afinidade com feitiços de natureza e encantamento.",
            "Destreza Élfica: +2 em Destreza.",
        ],
    },
    {
        "slug": "orc",
        "name": "Orc",
        "summary": "Guerreiros de força brutal, orgulho feroz e resistência elevada em combate.",
        "traits": [
            "Fúria Orc: aumento temporário de força e resistência.",
            "Resistência de Guerra: maior durabilidade física.",
            "Força Bruta: +2 em Força.",
        ],
    },
    {
        "slug": "tiefling",
        "name": "Tiefling",
        "summary": "Descendentes de sangue infernal, marcados por traços demoníacos e dons sombrios.",
        "traits": [
            "Sangue Demoníaco: afinidade com magia sombria e fogo.",
            "Charme Sobrenatural: bônus em interações sociais.",
            "Resistência ao Fogo: resistência elevada contra fogo.",
        ],
    },
    {
        "slug": "halfling",
        "name": "Halfling",
        "summary": "Pequenos, discretos e surpreendentemente corajosos, guiados pela sorte e agilidade.",
        "traits": [
            "Sorte Halfling: pode rerrolar uma falha crítica por descanso longo.",
            "Agilidade: movimentação leve e rápida.",
            "Pequenos e Ágeis: +2 em Destreza.",
        ],
    },
    {
        "slug": "anjo",
        "name": "Anjo",
        "summary": "Seres celestiais de luz, beleza e disciplina divina, marcados por presença inspiradora.",
        "traits": [
            "Aura Celestial: cura leve ou bônus temporários em combate.",
            "Voo Angelical: capacidade de planar ou voar por curtos períodos.",
            "Luz Divina: +2 em Carisma e Sabedoria.",
        ],
        "requirement": "Requer teste d20 com resultado 15 ou mais para acesso normal.",
        "threshold": 15,
        "inferior_name": "Anjo Inferior",
        "inferior_summary": "Um ser tocado pelo céu, mas ainda não reconhecido como celestial pleno. Precisa provar seu valor para ascender.",
    },
    {
        "slug": "demonio",
        "name": "Demônio",
        "summary": "Entidades infernais ferozes, ligadas ao caos, ao fogo sombrio e à manipulação.",
        "traits": [
            "Chamas Infernais: poder ofensivo ligado ao fogo demoníaco.",
            "Teletransporte Sombrio: movimentação rápida entre sombras.",
            "Força Infernal: +2 em Força ou Destreza.",
        ],
        "requirement": "Requer teste d20 com resultado 16 ou mais para acesso normal.",
        "threshold": 16,
        "inferior_name": "Demônio Inferior",
        "inferior_summary": "Um ser marcado pelo inferno, porém ainda sem a plenitude infernal. Precisa provar seu valor para ascender.",
    },
    {
        "slug": "gnomo",
        "name": "Gnomo",
        "summary": "Criativos, engenhosos e inteligentes, com afinidade natural por invenções e ilusão.",
        "traits": [
            "Inventores Brilhantes: talento com ferramentas e invenções mágicas.",
            "Ilusão Mágica: proficiência em magia ilusória.",
            "Inteligência Brilhante: +2 em Inteligência.",
        ],
    },
    {
        "slug": "meio-elfo",
        "name": "Meio-Elfo",
        "summary": "Herdeiros do melhor entre humanos e elfos, combinando carisma, flexibilidade e sensibilidade.",
        "traits": [
            "Flexibilidade Mágica: acesso a feitiços de herança humana e élfica.",
            "Charme e Carisma: grande facilidade em interações sociais.",
            "Destreza e Carisma: +1 em Destreza e Carisma.",
        ],
    },
]

ATTRIBUTE_FIELDS = [
    ("strength", "FOR"),
    ("dexterity", "DEX"),
    ("constitution", "CON"),
    ("intelligence", "INT"),
    ("wisdom", "SAB"),
    ("charisma", "CAR"),
    ("perception", "PER"),
]

CLASSES = [
    {"slug": "wizard", "name": "Wizard", "summary": "Mestre da magia arcana e da manipulação elemental.", "requirements": {"intelligence": 12}},
    {"slug": "barbarian", "name": "Barbarian", "summary": "Combatente brutal guiado por fúria e resistência.", "requirements": {"strength": 12, "constitution": 10}},
    {"slug": "bard", "name": "Bard", "summary": "Encanta aliados e inimigos com música, palavra e presença.", "requirements": {"charisma": 12, "dexterity": 10}},
    {"slug": "cleric", "name": "Cleric", "summary": "Canaliza poder divino para cura, proteção e julgamento.", "requirements": {"wisdom": 12, "charisma": 10}},
    {"slug": "druid", "name": "Druid", "summary": "Guardião da natureza e dos espíritos antigos.", "requirements": {"wisdom": 12, "constitution": 10}},
    {"slug": "fighter", "name": "Fighter", "summary": "Especialista em combate, técnica e liderança de campo.", "requirements": {"strength": 12, "dexterity": 10}},
    {"slug": "rogue", "name": "Rogue", "summary": "Furtividade, precisão e manipulação nas sombras.", "requirements": {"dexterity": 12, "intelligence": 9}},
    {"slug": "necromancer", "name": "Necromancer", "summary": "Usuário das artes sombrias e do domínio sobre mortos e almas.", "requirements": {"intelligence": 12, "wisdom": 10}},
    {"slug": "summoner", "name": "Summoner", "summary": "Invoca criaturas e forças de outros planos.", "requirements": {"intelligence": 12, "charisma": 10}},
    {"slug": "monk", "name": "Monk", "summary": "Disciplina física e espiritual canalizada pelo Ki.", "requirements": {"dexterity": 12, "wisdom": 10}},
    {"slug": "demon-hunter", "name": "Demon Hunter", "summary": "Caçador especializado em demônios e corrupção.", "requirements": {"strength": 12, "dexterity": 10}},
    {"slug": "sem-classe", "name": "Sem Classe", "summary": "Um iniciado comum, ainda sem trilha definitiva.", "requirements": {}},
]

CLASS_LEVELS = {
    "wizard": [
        {"title": "Aprendiz Arcano", "requirement": "5 batalhas ou missoes bem-sucedidas", "reward": "+2 INT, +1 SAB"},
        {"title": "Conjurador", "requirement": "10 batalhas ou 1 missao importante", "reward": "+2 INT, +2 SAB"},
        {"title": "Magus", "requirement": "20 batalhas ou 3 missoes significativas", "reward": "+3 INT, +1 SAB"},
        {"title": "Erudito Arcano", "requirement": "30 batalhas ou 5 missoes de alto risco", "reward": "+3 INT, +2 SAB"},
        {"title": "Arquimago da Sabedoria", "requirement": "50 batalhas ou 10 missoes-chave", "reward": "+4 INT, +3 SAB"},
    ],
    "barbarian": [
        {"title": "Iniciado Selvagem", "requirement": "5 batalhas ou missoes com combate intenso", "reward": "+2 FOR, +1 CON"},
        {"title": "Berserker", "requirement": "10 batalhas ou 2 missoes de grande perigo", "reward": "+2 FOR, +2 CON"},
        {"title": "Mestre do Grito de Guerra", "requirement": "20 batalhas ou 3 missoes epicas", "reward": "+3 FOR, +1 CON"},
        {"title": "Espirito Primordial", "requirement": "30 batalhas ou 5 vitorias contra grandes inimigos", "reward": "+3 FOR, +2 CON"},
        {"title": "Devorador de Tempestades", "requirement": "50 batalhas ou 10 combates de alta dificuldade", "reward": "+4 FOR, +3 CON"},
    ],
    "bard": [
        {"title": "Trovador", "requirement": "5 apresentacoes ou interacoes influentes", "reward": "+2 CAR, +1 DEX"},
        {"title": "Encantador", "requirement": "10 performances ou dialogos importantes", "reward": "+2 CAR, +2 DEX"},
        {"title": "Virtuoso", "requirement": "20 performances notaveis ou missoes sociais", "reward": "+3 CAR, +1 DEX"},
        {"title": "Maestro Arcano", "requirement": "30 performances impressionantes ou eventos-chave", "reward": "+3 CAR, +2 DEX"},
        {"title": "Sabio das Harmonias", "requirement": "50 performances excepcionais ou 10 missoes influentes", "reward": "+4 CAR, +3 DEX"},
    ],
    "cleric": [
        {"title": "Acolito", "requirement": "5 rituais ou atos de cura", "reward": "+2 SAB, +1 CAR"},
        {"title": "Discipulo Divino", "requirement": "10 curas ou rituais sagrados significativos", "reward": "+2 SAB, +2 CAR"},
        {"title": "Paladino da Fe", "requirement": "20 missoes em defesa da fe", "reward": "+3 SAB, +1 CAR"},
        {"title": "Profeta", "requirement": "30 visoes divinas ou revelacoes", "reward": "+3 SAB, +2 CAR"},
        {"title": "Avatar da Divindade", "requirement": "50 missoes de importancia divina", "reward": "+4 SAB, +3 CAR"},
    ],
    "druid": [
        {"title": "Guardiao das Florestas", "requirement": "5 missoes de protecao ambiental", "reward": "+2 SAB, +1 CON"},
        {"title": "Chamado da Natureza", "requirement": "10 missoes de restauracao natural", "reward": "+2 SAB, +2 CON"},
        {"title": "Guardiao do Circulo", "requirement": "20 missoes em equilibrio com a natureza", "reward": "+3 SAB, +1 CON"},
        {"title": "Sabio dos Espiritos", "requirement": "30 missoes espirituais", "reward": "+3 SAB, +2 CON"},
        {"title": "Avatara da Natureza", "requirement": "50 missoes de grande risco pela natureza", "reward": "+4 SAB, +3 CON"},
    ],
    "fighter": [
        {"title": "Soldado", "requirement": "5 batalhas ou missoes de combate", "reward": "+2 FOR, +1 DEX"},
        {"title": "Combatente", "requirement": "10 batalhas ou 2 missoes taticas", "reward": "+2 FOR, +2 DEX"},
        {"title": "Cavaleiro", "requirement": "20 batalhas ou 3 missoes de defesa", "reward": "+3 FOR, +1 DEX"},
        {"title": "Guerreiro Tatico", "requirement": "30 batalhas ou 5 vitorias taticas", "reward": "+3 FOR, +2 DEX"},
        {"title": "Campeao", "requirement": "50 batalhas ou 10 vitorias de alto nivel", "reward": "+4 FOR, +3 DEX"},
    ],
    "rogue": [
        {"title": "Ladrao", "requirement": "5 furtos ou missoes de infiltracao", "reward": "+2 DEX, +1 INT"},
        {"title": "Assassino", "requirement": "10 missoes de eliminacao ou infiltracao", "reward": "+2 DEX, +2 INT"},
        {"title": "Trapaceiro", "requirement": "20 missoes de manipulacao", "reward": "+3 DEX, +1 INT"},
        {"title": "Mestre do Disfarce", "requirement": "30 missoes com disfarce ou manipulacao", "reward": "+3 DEX, +2 INT"},
        {"title": "Sombra Suprema", "requirement": "50 missoes de alta infiltracao", "reward": "+4 DEX, +3 INT"},
    ],
    "necromancer": [
        {"title": "Aprendiz da Morte", "requirement": "5 rituais ou evocacoes de baixo nivel", "reward": "+2 INT, +1 SAB"},
        {"title": "Evocador de Almas", "requirement": "10 rituais ou invocacoes de espiritos fracos", "reward": "+2 INT, +2 SAB"},
        {"title": "Senhor das Sombras", "requirement": "20 missoes com mortos ou espiritos", "reward": "+3 INT, +1 SAB"},
        {"title": "Mestre Necromante", "requirement": "30 invocacoes poderosas", "reward": "+3 INT, +2 SAB"},
        {"title": "Rei Lich", "requirement": "50 rituais de necromancia", "reward": "+4 INT, +3 SAB"},
    ],
    "summoner": [
        {"title": "Conjurador Menor", "requirement": "5 invocacoes de baixo poder", "reward": "+2 INT, +1 CAR"},
        {"title": "Invocador de Almas", "requirement": "10 invocacoes intermediarias", "reward": "+2 INT, +2 CAR"},
        {"title": "Mestre dos Elementos", "requirement": "20 invocacoes elementares", "reward": "+3 INT, +1 CAR"},
        {"title": "Conjurador Supremo", "requirement": "30 invocacoes de criaturas poderosas", "reward": "+3 INT, +2 CAR"},
        {"title": "Senhor dos Planos", "requirement": "50 invocacoes extraordinarias", "reward": "+4 INT, +3 CAR"},
    ],
    "monk": [
        {"title": "Discipulo da Serenidade", "requirement": "5 missoes de meditacao ou treino", "reward": "+2 DEX, +1 SAB"},
        {"title": "Guerreiro Interior", "requirement": "10 missoes de superacao mental", "reward": "+2 DEX, +2 SAB"},
        {"title": "Mestre do Ki", "requirement": "20 missoes de grande concentracao", "reward": "+3 DEX, +1 SAB"},
        {"title": "Sombra do Fogo", "requirement": "30 missoes de dominio do Ki em combate", "reward": "+3 DEX, +2 SAB"},
        {"title": "Avatar do Ki", "requirement": "50 missoes de aperfeicoamento espiritual", "reward": "+4 DEX, +3 SAB"},
    ],
    "demon-hunter": [
        {"title": "Rastreador", "requirement": "5 missoes de caca a demonios", "reward": "+2 FOR, +1 DEX"},
        {"title": "Cacador Implacavel", "requirement": "10 missoes de combate ou armadilhas", "reward": "+2 FOR, +2 DEX"},
        {"title": "Exterminador", "requirement": "20 demonios derrotados ou missoes de alto risco", "reward": "+3 FOR, +1 DEX"},
        {"title": "Justiceiro", "requirement": "30 missoes de eliminacao de grandes demonios", "reward": "+3 FOR, +2 DEX"},
        {"title": "Ascendente", "requirement": "50 grandes cacadas ou derrotas poderosas", "reward": "+4 FOR, +3 DEX"},
    ],
    "sem-classe": [
        {"title": "Iniciado Comum", "requirement": "Sem requisitos especiais", "reward": "Evolucao livre ate encontrar uma trilha"},
    ],
}

for class_definition in CLASSES:
    class_definition["levels"] = CLASS_LEVELS.get(class_definition["slug"], [])
