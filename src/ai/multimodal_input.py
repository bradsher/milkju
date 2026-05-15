"""多模态输入数据结构

提供统一的多模态输入封装，支持文字、图片、文件、音频等多种媒体类型。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Literal
from pathlib import Path
import base64
import mimetypes


@dataclass
class MediaInput:
    """媒体输入（图片、音频、文件）
    
    Attributes:
        type: 媒体类型
        data: Base64编码的数据
        mime_type: MIME类型
        filename: 文件名
    """
    
    type: Literal['image', 'audio', 'file', 'video']
    data: str  # Base64编码
    mime_type: Optional[str] = None
    filename: Optional[str] = None
    
    @classmethod
    def from_file(cls, file_path: str, media_type: Literal['image', 'audio', 'file']) -> MediaInput:
        """从文件创建媒体输入
        
        Args:
            file_path: 文件路径
            media_type: 媒体类型
            
        Returns:
            MediaInput实例
        """
        path = Path(file_path)
        mime_type = mimetypes.guess_type(str(path))[0]
        
        with open(path, 'rb') as f:
            data = base64.b64encode(f.read()).decode('utf-8')
        
        return cls(
            type=media_type,
            data=data,
            mime_type=mime_type,
            filename=path.name
        )
    
    @classmethod
    def from_base64(
        cls, 
        base64_data: str, 
        media_type: Literal['image', 'audio', 'file'],
        mime_type: Optional[str] = None,
        filename: Optional[str] = None
    ) -> MediaInput:
        """从Base64数据创建媒体输入
        
        Args:
            base64_data: Base64编码的数据
            media_type: 媒体类型
            mime_type: MIME类型
            filename: 文件名
            
        Returns:
            MediaInput实例
        """
        return cls(
            type=media_type,
            data=base64_data,
            mime_type=mime_type,
            filename=filename
        )


@dataclass
class MultimodalInput:
    """多模态输入封装
    
    支持文字+图片+文件+音频的组合输入。
    
    Example:
        >>> input_data = MultimodalInput(text="分析这张图片")
        >>> input_data.add_image(base64_image_data)
        >>> input_data.add_file("/path/to/document.pdf")
    """
    
    text: str  # 文本内容（必需）
    media: List[MediaInput] = field(default_factory=list)  # 媒体列表
    
    def add_image(self, image_data: str, mime_type: str = 'image/jpeg', filename: Optional[str] = None):
        """添加图片
        
        Args:
            image_data: Base64编码的图片数据
            mime_type: MIME类型
            filename: 文件名
        """
        self.media.append(
            MediaInput.from_base64(image_data, 'image', mime_type, filename)
        )
    
    def add_file(self, file_path: str):
        """从文件路径添加文件
        
        Args:
            file_path: 文件路径
        """
        self.media.append(
            MediaInput.from_file(file_path, 'file')
        )
    
    def add_file_base64(self, file_data: str, mime_type: str, filename: str):
        """从Base64添加文件
        
        Args:
            file_data: Base64编码的文件数据
            mime_type: MIME类型
            filename: 文件名
        """
        self.media.append(
            MediaInput.from_base64(file_data, 'file', mime_type, filename)
        )
    
    def add_audio(self, audio_data: str, mime_type: str = 'audio/mpeg', filename: Optional[str] = None):
        """添加音频
        
        Args:
            audio_data: Base64编码的音频数据
            mime_type: MIME类型
            filename: 文件名
        """
        self.media.append(
            MediaInput.from_base64(audio_data, 'audio', mime_type, filename)
        )
        
    def add_video(self, video_data: str, mime_type: str = 'video/mp4', filename: Optional[str] = None):
        """添加视频
        
        Args:
            video_data: Base64编码的视频数据
            mime_type: MIME类型
            filename: 文件名
        """
        self.media.append(
            MediaInput.from_base64(video_data, 'video', mime_type, filename)
        )
    
    @property
    def has_media(self) -> bool:
        """是否包含媒体"""
        return len(self.media) > 0
    
    @property
    def has_image(self) -> bool:
        """是否包含图片"""
        return any(m.type == 'image' for m in self.media)
    
    @property
    def has_file(self) -> bool:
        """是否包含文件"""
        return any(m.type == 'file' for m in self.media)
    
    @property
    def has_audio(self) -> bool:
        """是否包含音频"""
        return any(m.type == 'audio' for m in self.media)

    @property
    def has_video(self) -> bool:
        """是否包含视频"""
        # Video is currently mapped to 'file' type with video mime_type, 
        # or we might add explicit 'video' type later.
        # Based on previous chat_handlers logic, video might be passed as generic file or media.
        # But let's check for 'video' type if we decide to use it, or check mimetype.
        for m in self.media:
            if m.type == 'video': 
                return True
            if m.type == 'file' and m.mime_type and m.mime_type.startswith('video/'):
                return True
        return False
    
    def get_first_image(self) -> Optional[MediaInput]:
        """获取第一张图片"""
        for m in self.media:
            if m.type == 'image':
                return m
        return None
