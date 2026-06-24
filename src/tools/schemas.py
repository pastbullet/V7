"""SpecIndex tool schemas in OpenAI function-calling format."""

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "get_document_structure",
            "description": (
                "Read the document structure index. Use this first to locate relevant "
                "sections and page ranges before reading page content."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_name": {
                        "type": "string",
                        "description": "Document name, for example FC-LS.pdf or rfc5880-BFD.pdf.",
                    },
                    "part": {
                        "type": "integer",
                        "description": "Structure chunk number, starting at 1.",
                        "default": 1,
                    },
                },
                "required": ["doc_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_page_content",
            "description": (
                "Read one or more pages selected from the structure index. The page "
                "response should provide text spans and asset references when available."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_name": {
                        "type": "string",
                        "description": "Document name, for example FC-LS.pdf or rfc5880-BFD.pdf.",
                    },
                    "pages": {
                        "type": "string",
                        "description": "Page spec such as '7', '7-11', '7,9,11', or mixed pages/ranges like '36,166-170,179,203'.",
                    },
                },
                "required": ["doc_name", "pages"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_assets",
            "description": (
                "List stable table and figure assets for a document, optionally filtered "
                "by page range, section, or asset type."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {
                        "type": "string",
                        "description": "Processed SpecIndex document id.",
                    },
                    "page_range": {
                        "type": "string",
                        "description": "Optional page range such as '149-151' or mixed pages/ranges like '36,166-170,179,203'.",
                    },
                    "section_id": {
                        "type": "string",
                        "description": "Optional structure section id.",
                    },
                    "type": {
                        "type": "string",
                        "enum": ["table", "figure"],
                        "description": "Optional asset type filter.",
                    },
                    "caption_query": {
                        "type": "string",
                        "description": "Optional case-insensitive substring filter over asset captions, useful for locating referenced table or figure numbers.",
                    },
                },
                "required": ["doc_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_table",
            "description": (
                "Read a logical table asset. Use this before making claims about a table, "
                "including field names, widths, values, conditions, or continuation rows."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "table_id": {
                        "type": "string",
                        "description": "Stable table asset id.",
                    },
                    "doc_id": {
                        "type": "string",
                        "description": "Optional processed SpecIndex document id.",
                    },
                    "view": {
                        "type": "string",
                        "enum": ["full", "summary"],
                        "description": "Return full table by default.",
                        "default": "full",
                    },
                },
                "required": ["table_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_image",
            "description": (
                "Read a figure/image asset. Use this before making claims about diagrams, "
                "frame layouts, state diagrams, or visual regions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "string",
                        "description": "Stable figure/image asset id.",
                    },
                    "doc_id": {
                        "type": "string",
                        "description": "Optional processed SpecIndex document id.",
                    },
                    "view": {
                        "type": "string",
                        "enum": ["full", "summary"],
                        "description": "Return full image metadata by default.",
                        "default": "full",
                    },
                },
                "required": ["image_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify_evidence",
            "description": (
                "Structurally verify claim evidence refs. This checks that span/cell/crop "
                "objects exist and optional quotes are contained in the raw object; it does "
                "not judge protocol semantics."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {
                        "type": "string",
                        "description": "Processed SpecIndex document id.",
                    },
                    "claim": {
                        "type": "string",
                        "description": "The claim being supported.",
                    },
                    "evidence_refs": {
                        "type": "array",
                        "description": (
                            "Raw evidence refs in canonical flat form. Accepted types are "
                            "text_span, table_cell, figure_crop, and figure_region."
                        ),
                        "items": {
                            "oneOf": [
                                {
                                    "type": "object",
                                    "properties": {
                                        "type": {"type": "string", "enum": ["text_span"]},
                                        "span_id": {"type": "string"},
                                        "quote": {"type": "string"},
                                    },
                                    "required": ["type", "span_id"],
                                    "additionalProperties": True,
                                },
                                {
                                    "type": "object",
                                    "properties": {
                                        "type": {"type": "string", "enum": ["table_cell"]},
                                        "asset_id": {"type": "string"},
                                        "cell_id": {"type": "string"},
                                        "quote": {"type": "string"},
                                    },
                                    "required": ["type", "asset_id", "cell_id"],
                                    "additionalProperties": True,
                                },
                                {
                                    "type": "object",
                                    "properties": {
                                        "type": {"type": "string", "enum": ["figure_crop"]},
                                        "asset_id": {"type": "string"},
                                    },
                                    "required": ["type", "asset_id"],
                                    "additionalProperties": True,
                                },
                                {
                                    "type": "object",
                                    "properties": {
                                        "type": {"type": "string", "enum": ["figure_region"]},
                                        "asset_id": {"type": "string"},
                                        "region_id": {"type": "string"},
                                        "bbox": {
                                            "type": "array",
                                            "items": {"type": "number"},
                                        },
                                    },
                                    "required": ["type", "asset_id"],
                                    "additionalProperties": True,
                                },
                            ],
                        },
                    },
                },
                "required": ["doc_id", "claim", "evidence_refs"],
            },
        },
    },
]


def get_tool_schemas() -> list[dict]:
    """Return tool schemas."""
    return TOOL_SCHEMAS


def convert_to_anthropic_format(schemas: list[dict]) -> list[dict]:
    """Convert OpenAI function-calling schema to Anthropic tool schema."""
    result = []
    for schema in schemas:
        func = schema["function"]
        result.append(
            {
                "name": func["name"],
                "description": func["description"],
                "input_schema": func["parameters"],
            }
        )
    return result
