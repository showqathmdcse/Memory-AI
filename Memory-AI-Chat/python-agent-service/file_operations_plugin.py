"""
File Operations Plugin for LangChain Agent
Real file operations that can be used directly in Python (not JSON commands)
"""

import os
import re
import logging
from pathlib import Path
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from langchain.tools import StructuredTool

logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic Schemas for Tool Input Validation
# ============================================================================

class ReadFileInput(BaseModel):
    """Input schema for read_file tool"""
    path: str = Field(description="The relative path to the file from workspace root")


class WriteFileInput(BaseModel):
    """Input schema for write_file tool"""
    path: str = Field(description="The relative path to the file")
    content: str = Field(description="The complete content to write to the file")


class AppendFileInput(BaseModel):
    """Input schema for append_file tool"""
    path: str = Field(description="The relative path to the file")
    content: str = Field(description="The content to append to the file")


class DeleteFileInput(BaseModel):
    """Input schema for delete_file tool"""
    path: str = Field(description="The relative path to the file to delete")


class ListFilesInput(BaseModel):
    """Input schema for list_files tool"""
    path: str = Field(description="The directory path to list")
    recursive: bool = Field(default=False, description="Whether to list files recursively")
    pattern: Optional[str] = Field(default=None, description="Optional glob pattern to filter files (e.g., '*.py')")


class SearchFilesInput(BaseModel):
    """Input schema for search_files tool"""
    path: str = Field(description="The directory path to search in")
    pattern: str = Field(description="The regex pattern to search for")
    file_extension: Optional[str] = Field(default=None, description="Optional file extension to filter (e.g., '.py', '.txt')")


class CreateDirectoryInput(BaseModel):
    """Input schema for create_directory tool"""
    path: str = Field(description="The directory path to create")


class FileExistsInput(BaseModel):
    """Input schema for file_exists tool"""
    path: str = Field(description="The file or directory path to check")


# ============================================================================
# File Operation Functions
# ============================================================================

def read_file(path: str) -> str:
    """
    Read the contents of a file.
    
    Args:
        path: Relative or absolute path to the file
        
    Returns:
        File contents as string
        
    Raises:
        FileNotFoundError: If file doesn't exist
        IOError: If file cannot be read
    """
    try:
        file_path = Path(path).resolve()
        logger.info(f"Reading file: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        logger.info(f"Successfully read {len(content)} characters from {file_path}")
        return content
        
    except FileNotFoundError:
        error_msg = f"File not found: {path}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)
    except Exception as e:
        error_msg = f"Error reading file {path}: {str(e)}"
        logger.error(error_msg)
        raise IOError(error_msg)


def write_file(path: str, content: str) -> str:
    """
    Write content to a file (creates or overwrites).
    
    Args:
        path: Relative or absolute path to the file
        content: Content to write to the file
        
    Returns:
        Success message with file path
    """
    try:
        file_path = Path(path).resolve()
        
        # Create parent directories if they don't exist
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Writing to file: {file_path}")
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        success_msg = f"Successfully wrote {len(content)} characters to {file_path}"
        logger.info(success_msg)
        return success_msg
        
    except Exception as e:
        error_msg = f"Error writing to file {path}: {str(e)}"
        logger.error(error_msg)
        raise IOError(error_msg)


def append_file(path: str, content: str) -> str:
    """
    Append content to an existing file.
    
    Args:
        path: Relative or absolute path to the file
        content: Content to append to the file
        
    Returns:
        Success message with file path
    """
    try:
        file_path = Path(path).resolve()
        
        # Create file if it doesn't exist
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Appending to file: {file_path}")
        
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(content)
        
        success_msg = f"Successfully appended {len(content)} characters to {file_path}"
        logger.info(success_msg)
        return success_msg
        
    except Exception as e:
        error_msg = f"Error appending to file {path}: {str(e)}"
        logger.error(error_msg)
        raise IOError(error_msg)


def delete_file(path: str) -> str:
    """
    Delete a file.
    
    Args:
        path: Relative or absolute path to the file
        
    Returns:
        Success message
    """
    try:
        file_path = Path(path).resolve()
        logger.info(f"Deleting file: {file_path}")
        
        if file_path.is_file():
            file_path.unlink()
            success_msg = f"Successfully deleted file: {file_path}"
            logger.info(success_msg)
            return success_msg
        else:
            error_msg = f"Not a file or doesn't exist: {path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
            
    except Exception as e:
        error_msg = f"Error deleting file {path}: {str(e)}"
        logger.error(error_msg)
        raise IOError(error_msg)


def list_files(path: str, recursive: bool = False, pattern: Optional[str] = None) -> str:
    """
    List files in a directory.
    
    Args:
        path: Directory path
        recursive: Whether to list files recursively
        pattern: Optional glob pattern to filter files
        
    Returns:
        Formatted string with file listing
    """
    try:
        dir_path = Path(path).resolve()
        logger.info(f"Listing files in: {dir_path} (recursive={recursive}, pattern={pattern})")
        
        if not dir_path.is_dir():
            error_msg = f"Not a directory: {path}"
            logger.error(error_msg)
            raise NotADirectoryError(error_msg)
        
        files = []
        
        if recursive:
            if pattern:
                files = list(dir_path.rglob(pattern))
            else:
                files = list(dir_path.rglob('*'))
        else:
            if pattern:
                files = list(dir_path.glob(pattern))
            else:
                files = list(dir_path.glob('*'))
        
        # Sort and format output
        files = sorted(files)
        file_list = []
        
        for file in files:
            relative_path = file.relative_to(dir_path)
            file_type = "DIR" if file.is_dir() else "FILE"
            size = file.stat().st_size if file.is_file() else 0
            file_list.append(f"{file_type:5} {size:>10} bytes  {relative_path}")
        
        result = f"Found {len(file_list)} items in {dir_path}:\n" + "\n".join(file_list)
        logger.info(f"Listed {len(file_list)} items")
        return result
        
    except Exception as e:
        error_msg = f"Error listing files in {path}: {str(e)}"
        logger.error(error_msg)
        raise IOError(error_msg)


def search_files(path: str, pattern: str, file_extension: Optional[str] = None) -> str:
    """
    Search for text patterns in files using regex.
    
    Args:
        path: Directory path to search
        pattern: Regex pattern to search for
        file_extension: Optional file extension filter (e.g., '.py')
        
    Returns:
        Formatted string with search results
    """
    try:
        dir_path = Path(path).resolve()
        logger.info(f"Searching in: {dir_path} for pattern: {pattern}")
        
        if not dir_path.is_dir():
            error_msg = f"Not a directory: {path}"
            logger.error(error_msg)
            raise NotADirectoryError(error_msg)
        
        regex = re.compile(pattern)
        results = []
        
        # Get all files
        if file_extension:
            files = dir_path.rglob(f'*{file_extension}')
        else:
            files = dir_path.rglob('*')
        
        for file_path in files:
            if not file_path.is_file():
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        if regex.search(line):
                            relative_path = file_path.relative_to(dir_path)
                            results.append(f"{relative_path}:{line_num}: {line.strip()}")
            except Exception as e:
                logger.warning(f"Could not read file {file_path}: {e}")
                continue
        
        if results:
            result_text = f"Found {len(results)} matches:\n" + "\n".join(results[:50])
            if len(results) > 50:
                result_text += f"\n... and {len(results) - 50} more matches"
        else:
            result_text = f"No matches found for pattern: {pattern}"
        
        logger.info(f"Search complete: {len(results)} matches found")
        return result_text
        
    except Exception as e:
        error_msg = f"Error searching files in {path}: {str(e)}"
        logger.error(error_msg)
        raise IOError(error_msg)


def create_directory(path: str) -> str:
    """
    Create a directory (and parent directories if needed).
    
    Args:
        path: Directory path to create
        
    Returns:
        Success message
    """
    try:
        dir_path = Path(path).resolve()
        logger.info(f"Creating directory: {dir_path}")
        
        dir_path.mkdir(parents=True, exist_ok=True)
        
        success_msg = f"Successfully created directory: {dir_path}"
        logger.info(success_msg)
        return success_msg
        
    except Exception as e:
        error_msg = f"Error creating directory {path}: {str(e)}"
        logger.error(error_msg)
        raise IOError(error_msg)


def file_exists(path: str) -> str:
    """
    Check if a file or directory exists.
    
    Args:
        path: File or directory path to check
        
    Returns:
        String indicating existence and type
    """
    try:
        file_path = Path(path).resolve()
        
        if file_path.is_file():
            return f"EXISTS: {file_path} (file)"
        elif file_path.is_dir():
            return f"EXISTS: {file_path} (directory)"
        else:
            return f"NOT FOUND: {path}"
            
    except Exception as e:
        error_msg = f"Error checking path {path}: {str(e)}"
        logger.error(error_msg)
        raise IOError(error_msg)


# ============================================================================
# Create LangChain Tools
# ============================================================================

def create_file_operation_tools() -> List[StructuredTool]:
    """
    Create LangChain StructuredTools for file operations.
    
    Returns:
        List of StructuredTool instances
    """
    tools = [
        StructuredTool.from_function(
            func=read_file,
            name="read_file",
            description="Read the contents of a file. Returns the file contents as a string.",
            args_schema=ReadFileInput
        ),
        StructuredTool.from_function(
            func=write_file,
            name="write_file",
            description="Write content to a file (creates new file or overwrites existing). Creates parent directories if needed.",
            args_schema=WriteFileInput
        ),
        StructuredTool.from_function(
            func=append_file,
            name="append_file",
            description="Append content to the end of an existing file. Creates file if it doesn't exist.",
            args_schema=AppendFileInput
        ),
        StructuredTool.from_function(
            func=delete_file,
            name="delete_file",
            description="Delete a file. Use with caution - this action cannot be undone.",
            args_schema=DeleteFileInput
        ),
        StructuredTool.from_function(
            func=list_files,
            name="list_files",
            description="List files and directories in a specified path. Can list recursively and filter by pattern.",
            args_schema=ListFilesInput
        ),
        StructuredTool.from_function(
            func=search_files,
            name="search_files",
            description="Search for text patterns in files using regex. Can filter by file extension.",
            args_schema=SearchFilesInput
        ),
        StructuredTool.from_function(
            func=create_directory,
            name="create_directory",
            description="Create a directory and all parent directories as needed.",
            args_schema=CreateDirectoryInput
        ),
        StructuredTool.from_function(
            func=file_exists,
            name="file_exists",
            description="Check if a file or directory exists and return its type.",
            args_schema=FileExistsInput
        ),
    ]
    
    logger.info(f"Created {len(tools)} file operation tools")
    return tools


# ============================================================================
# Convenience Functions for Direct Python Usage
# ============================================================================

class FileOperations:
    """
    Convenience class for direct Python file operations.
    Use this when you want to call file operations directly from Python code.
    """
    
    @staticmethod
    def read(path: str) -> str:
        """Read file contents."""
        return read_file(path)
    
    @staticmethod
    def write(path: str, content: str) -> str:
        """Write to file."""
        return write_file(path, content)
    
    @staticmethod
    def append(path: str, content: str) -> str:
        """Append to file."""
        return append_file(path, content)
    
    @staticmethod
    def delete(path: str) -> str:
        """Delete file."""
        return delete_file(path)
    
    @staticmethod
    def list(path: str, recursive: bool = False, pattern: Optional[str] = None) -> str:
        """List files in directory."""
        return list_files(path, recursive, pattern)
    
    @staticmethod
    def search(path: str, pattern: str, file_extension: Optional[str] = None) -> str:
        """Search files for pattern."""
        return search_files(path, pattern, file_extension)
    
    @staticmethod
    def mkdir(path: str) -> str:
        """Create directory."""
        return create_directory(path)
    
    @staticmethod
    def exists(path: str) -> str:
        """Check if file/directory exists."""
        return file_exists(path)


# Global instance for convenience
file_ops = FileOperations()
