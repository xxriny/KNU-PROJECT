import { create } from 'zustand';
import { 
  applyNodeChanges, 
  applyEdgeChanges,
  addEdge,
} from '@xyflow/react';

// 1. 순수 상태만을 보관하는 Zustand 스토어
export const useERDStore = create(() => ({
  nodes: [],
  edges: [],
}));

// 2. No-Store-Actions 패턴: 스토어 외부에서 액션 함수 정의
export const onNodesChange = (changes) => {
  useERDStore.setState((state) => ({
    nodes: applyNodeChanges(changes, state.nodes),
  }));
};

export const onEdgesChange = (changes) => {
  useERDStore.setState((state) => ({
    edges: applyEdgeChanges(changes, state.edges),
  }));
};

export const onConnect = (connection) => {
  useERDStore.setState((state) => ({
    edges: addEdge({ ...connection, type: 'smart', animated: false }, state.edges),
  }));
};

export const setElements = (nodes, edges) => {
  useERDStore.setState({ nodes, edges });
};

