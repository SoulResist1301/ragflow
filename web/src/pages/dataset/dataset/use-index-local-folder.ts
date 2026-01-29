import { useSetModalState } from '@/hooks/common-hooks';
import { useRunDocument } from '@/hooks/use-document-request';
import { ResponseType } from '@/interfaces/database/base';
import { IDocumentInfo } from '@/interfaces/database/document';
import kbService from '@/services/knowledge-service';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { get } from 'lodash';
import { useCallback } from 'react';
import { useParams } from 'react-router';
import { DocumentApiAction } from '@/hooks/use-document-request';

export interface IIndexLocalFolderFormData {
  localPath: string;
  recursive: boolean;
  parseOnCreation: boolean;
}

export const useHandleIndexLocalFolder = () => {
  const {
    visible: indexLocalFolderVisible,
    hideModal: hideIndexLocalFolderModal,
    showModal: showIndexLocalFolderModal,
  } = useSetModalState();
  
  const queryClient = useQueryClient();
  const { id } = useParams();
  const { runDocumentByIds } = useRunDocument();

  const {
    data,
    isPending: loading,
    mutateAsync: indexLocalFolder,
  } = useMutation<
    ResponseType<{ indexed_count: number; files: IDocumentInfo[] }>,
    Error,
    IIndexLocalFolderFormData
  >({
    mutationKey: ['indexLocalFolder'],
    mutationFn: async ({ localPath, recursive }) => {
      try {
        const ret = await kbService.document_index_local_folder({
          kb_id: id!,
          local_path: localPath,
          recursive,
        });
        
        const code = get(ret, 'data.code');
        
        if (code === 0 || code === 500) {
          queryClient.invalidateQueries({
            queryKey: [DocumentApiAction.FetchDocumentList],
          });
        }
        
        return ret?.data;
      } catch (error) {
        console.warn(error);
        throw error;
      }
    },
  });

  const onIndexLocalFolderOk = useCallback(
    async ({ localPath, recursive, parseOnCreation }: IIndexLocalFolderFormData) => {
      const ret = await indexLocalFolder({ localPath, recursive, parseOnCreation });
      
      if (typeof ret?.message !== 'string') {
        return;
      }

      if (ret.code === 0 && parseOnCreation && ret.data?.files) {
        runDocumentByIds({
          documentIds: ret.data.files.map((x) => x.id),
          run: 1,
          shouldDelete: false,
        });
      }

      if (ret?.code === 0) {
        hideIndexLocalFolderModal();
      }
      
      return ret?.code;
    },
    [indexLocalFolder, runDocumentByIds, hideIndexLocalFolderModal],
  );

  return {
    indexLocalFolderLoading: loading,
    onIndexLocalFolderOk,
    indexLocalFolderVisible,
    hideIndexLocalFolderModal,
    showIndexLocalFolderModal,
    indexedData: data,
  };
};
