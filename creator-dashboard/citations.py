"""Bounded parsing of numeric bibliography citations, shared by writing and audit."""
import re

CITATION_RE = re.compile(r'\[(\d+(?:\s*[-–,;]\s*\d+)*)\]')


def numbers(group: str) -> list[int]:
    result=[]
    for item in re.split(r'\s*[,;]\s*',group):
        bounds=re.split(r'\s*[-–]\s*',item)
        if len(bounds)==1:
            result.append(int(bounds[0]))
        elif len(bounds)==2:
            first,last=map(int,bounds)
            if first>last or last-first>500:
                raise ValueError('Rentang sitasi tidak valid')
            result.extend(range(first,last+1))
        else:
            raise ValueError('Rentang sitasi tidak valid')
    return result
