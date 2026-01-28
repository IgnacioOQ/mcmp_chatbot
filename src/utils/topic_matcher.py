import re
from typing import List, Dict, Any

class TopicMatcher:
    def __init__(self, topics_structure: List[Dict[str, Any]]):
        """
        Initialize with the hierarchical research structure.
        Expected structure:
        [
            {
                "id": "logic",
                "name": "Logic",
                "subtopics": ["Philosophical Logic", "Modal Logic", ...]
            },
            ...
        ]
        """
        self.topics = topics_structure
        self._compile_keywords()

    def _compile_keywords(self):
        """
        Pre-compile keywords map for faster lookup.
        """
        self.keyword_map = {}
        for topic in self.topics:
            t_name = topic.get("name", "")
            if t_name:
                self.keyword_map[t_name.lower()] = topic["id"]
            
            # Subtopics mapping
            for sub in topic.get("subtopics", []):
                # Map subtopic text to (topic_id, subtopic_name)
                self.keyword_map[sub.lower()] = (topic["id"], sub)

    def match_interests(self, text: str) -> List[Dict[str, str]]:
        """
        Finds matching topics/subtopics in the text.
        Returns a list of structured matches:
        [
            {"topic_id": "logic", "topic_name": "Logic", "subtopic": "Philosophical Logic"},
            ...
        ]
        """
        if not text:
            return []
            
        text_lower = text.lower()
        matches = []
        seen = set()

        for keyword, mapped_value in self.keyword_map.items():
            # Simple substring match for now, can be improved with regex/spacy
            if keyword in text_lower:
                if isinstance(mapped_value, tuple):
                    # It's a subtopic
                    tid, sub = mapped_value
                    # Find parent name
                    parent = next((t for t in self.topics if t["id"] == tid), {})
                    entry = {
                        "topic_id": tid,
                        "topic_name": parent.get("name", ""),
                        "subtopic": sub
                    }
                else:
                    # It's a main topic
                    tid = mapped_value
                    parent = next((t for t in self.topics if t["id"] == tid), {})
                    entry = {
                        "topic_id": tid,
                        "topic_name": parent.get("name", ""),
                        "subtopic": None
                    }
                
                # Deduplicate based on ID + Subtopic
                key = f"{entry['topic_id']}:{entry['subtopic']}"
                if key not in seen:
                    matches.append(entry)
                    seen.add(key)
        
        return matches
