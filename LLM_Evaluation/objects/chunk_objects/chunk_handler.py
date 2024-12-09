"""
Class to chunk a document into chunks, merge too short chunks and get a list of atom chunks.
"""
import re
import copy
import logging as log
from objects.chunk_objects.chunk import MarkdownDocument, Chunk

class ChunkHandler:

    # define the order of split strings
    MARKDOWN_HEADINGS = ['# ', '## ', '### ', '#### ']

    RECOMMENDED_MIN_CHUNK_SIZE = 200
    RECOMMENDED_MAX_CHUNK_SIZE = 2500


    @staticmethod
    def split_by_bold_headers(text):
        # Regex pattern to match bold headers and the content that follows
        pattern = r'(?=\*\*.*?\*\*)'
        
        # Split the text into chunks where each chunk starts with a bold heading
        paragraphs = re.split(pattern, text)
        
        # Remove any empty chunks that may result from the split
        splits = [para.strip() for para in paragraphs if para.strip()]
        
        return splits

    
    
    @staticmethod
    def split_by_short_lines_that_might_be_headers(text):
        """
        When no markdown headers have been identified, 
        we search for lines with a short text consisting of 1 to 4 words 
        that have two line breaks before and after.
        """
        # Define the regex pattern to match up to 4 words separated by spaces between double newlines
        pattern = r'(?<=\n\n)(\w+(?: \w+){0,3})(?=\n\n)'
        
        # Split the text including the matched segments
        splits = re.split(pattern, text)
        
        # Combine every second split with the following split, ensuring no out-of-range errors
        combined_splits = [splits[0]]
        for i in range(1, len(splits), 2):
            if i + 1 < len(splits):
                combined_splits.append(splits[i] + splits[i+1])
            else:
                combined_splits.append(splits[i])
        
        return combined_splits
    
    
    @staticmethod
    def split_by_paragraphs(text):
        # Split the text into paragraphs
        splits = text.split('\n\n')
        return splits
    
    @staticmethod
    def split_by_sentence_with_line_break(text):
        # Regex pattern to match punctuation followed by a line break
        pattern = r'(?<=[.!?])\n'
        # Split the text using the pattern
        sentences = re.split(pattern, text)
        # Strip any leading/trailing whitespace from each sentence
        result = [sentence.strip() for sentence in sentences if sentence.strip()]
        return result
    
    @staticmethod
    def split_by_sentences(text):
        """CAUTION! DO NOT USE as will also split by abbreviations like 'Dr.' or 'Mr.' and enumerations like '1.2.3.'"""
        # Split the text into sentences
        raise NotImplementedError("""CAUTION! DO NOT USE as will also split by abbreviations like 'Dr.' or 'Mr.' and enumerations like '1.2.3.'""")
        splits = re.split(r'(?<=[.!?])\s', text)
        return splits
     
    @staticmethod
    def hard_split_by_character_number(text, max_size:int=-1):
        if max_size == -1: max_size = ChunkHandler.RECOMMENDED_MAX_CHUNK_SIZE - 1
        # follow best practice and overlay the chunks
        overlay_size = int(max_size/5)
        splits = []
        while len(text) >= max_size:
            splits.append(text[:max_size])
            text = text[max_size-overlay_size:]
        # also add the last piece of text
        splits.append(text)
        return splits
    
    
    @staticmethod
    def extract_page_numbers(text, remove_page_markers=False):
        """
        Removes the page markers from a chunk 
        and returns the cleaned text and a list of page numbers
        """
        # Regular expression to find page numbers within markers like '[Page 10]'
        # We match only the numbers, but remove the whole expression
        pattern = r'\n*\[PAGE (\d+)\]\n*'
        
        # Extract page numbers only
        matches = re.findall(pattern, text)
        page_numbers = [int(match) for match in matches]
        
        if remove_page_markers:
            # Remove the page markers from text
            cleaned_text = re.sub(pattern, '\n\n', text)
        else: cleaned_text = text

        # check if the text starts with a page number marker
        # in this case, the min page number is the page number of the chunk
        # otherwise, you should decrease the page number by 1
        text_starts_with_page_number = len(page_numbers) > 0 and text.strip().startswith(f'[PAGE {page_numbers[0]}]')

        return cleaned_text, page_numbers, text_starts_with_page_number


    @staticmethod
    def split_document_into_chunks(
        doc:MarkdownDocument, 
        max_chunk_size, 
        split_criteria, 
        recursive=True,
        include_page_number=True) -> list[Chunk]:

        
        # do not split if the chunk is not long
        if doc.len <= max_chunk_size:
            return []
        
        # We have a hierarchy of strings to split by defined in split_criteria.
        # If the doc cannot be splitted by the string of current level, increase the level until it gets splitted or reaches max level
        next_level = doc.chunk_level

        # DEBUG: uncomment to debug the splitting function for a single file 
        # if 'applications/applied-industries/medical-devices.md' in doc.file_path:
        #     pause = True

        if "Single-use components or systems" in doc.text and next_level == 1:
            debug = True
        
        # split by the next level
        for i_criterion, split_criterion in enumerate(split_criteria):

            if split_criterion in ChunkHandler.MARKDOWN_HEADINGS:
                regex_pattern = r"(?<!#)" + '\n'+split_criterion + r"(?!#)"
                # TODO: please change the regex pattern to exactly match the number of hashes... but be careful, it's a running system in the moment! ;)
                # regex_pattern = (r'\n' if split_criterion in ChunkHandler.MARKDOWN_HEADINGS else '') + f'{split_criterion}' \
                #     + (' ' if split_criterion in ChunkHandler.MARKDOWN_HEADINGS else '')
                # regex_pattern = f'{split_str}(?![#])'
                splits = re.split(regex_pattern, doc.text)

            elif callable(split_criterion):
                splits = split_criterion(doc.text)

            else:
                log.error(f'Splitting criteria {split_criterion} has unexpected type {type(split_criterion)}')
                continue

            # remove spaces and line breaks at beginning and end of strings
            splits = [item.strip() for item in splits]

            # if the document has not been splitted by the current level split string, go down to next level
            if len(splits) == 1:
                next_level += 1
                continue

            elif len(splits) > 1:                
                # if the split was by a markdwon heading, we add the split string back at the beginning of each chunk as it has been removed by the split function
                # but do not add it to the first chunk as the first chunk doesn't contain the splitting criteria string
                if split_criterion in ChunkHandler.MARKDOWN_HEADINGS:
                    if len(splits) == 1: 
                        splits = [split_criterion + splits[0]]
                    else:
                        splits = [splits[0]] + [f'{split_criterion}{split}' for split in splits[1:]]

                # remove empty splits or those only containing the split criterion
                # which happens when the split criterion is at the beginning of the text
                if type(split_criteria)==str:
                    splits = [split for split in splits if len(split.strip()) > (len(split_criterion)) ]
                else:
                    splits = [split for split in splits if len(split.strip()) > 0]

                # create a chunk for each split
                chunks = []
                # we want to add the page information to each chunk
                # some splits will not have a page info and should use the previously available info
                # the chunk's page is the same or bigger as the page number of its parent
                page_number = doc.page_number

                # ITERATE OVER ALL SPLITS
                for pos, split in enumerate(splits):
                    # remove the page tags in the split and remember the page numbers
                    split, page_numbers, chunk_starts_with_page_number = ChunkHandler.extract_page_numbers(split, False)
                    # use the smallest extracted number of the previous page number
                    if page_numbers: 
                        page_number = min(page_numbers)
                        # subsctract 1 as the extracted page number indicate the start of the NEXT page
                        # don't substract if it is the first page
                        # TODO: might be a bug, make sure, we do not subsctract -1 too often when a split does not contain page info
                        if page_number > 1 and not chunk_starts_with_page_number: page_number -= 1 
                    
                    # # for short splits, just use the title of the parent
                    # title_of_the_split = doc.title if len(split) < 100 else None

                    # instantiate the chunk
                    if "1.1 Background" in split: 
                        breakpoint = True
                    chunk = Chunk(split, doc, next_level+1, pos, page_number)
                    if recursive:
                        chunk.chunks = ChunkHandler.split_document_into_chunks(
                            chunk, max_chunk_size, split_criteria[i_criterion+1:], recursive, include_page_number)
                    chunks.append(chunk)

                    # set the maximum extracted page to current page number
                    page_number = max(page_numbers) if page_numbers else page_number

                if chunks is None:
                    pause = True
                return chunks
        
        # return an empty list of chunks if there was nothing to chunk
        log.info(f'Document {doc} has not be splitted into any chunks. Document length is: {doc.len}.')
        return []
        
    @staticmethod
    def merge_too_short_chunks(doc:MarkdownDocument, min_chunk_size, recursive=True) -> list[Chunk]:
        """
        Short chunks should be merged with other chunks to create a meaningful embedding.
        Merging strategy: iterate over all chunks. If a chunks is too short, add it to a list of chunks to be merged.
        If the next chunk together with the chunks to be merged would be long enough, sum all chunks together and create new chunk. 
        Maintain only the new merged chunk, drop too short chunks. When iteration over all chunks completed and 
        there is still not enough text for a chunk, still combine all chunks into a single one. 
        """
        raise DeprecationWarning(\
            "This function is deprecated. "
            "Use merge_short_chunks function in pipelines/02_markdown_to_chunks_pipeline.ipynb instead.")
    
        # if there are no chunks, there is nothing to merge
        if not doc.chunks: return doc.chunks

        # if there is a single chunk, we should check if its subchunks can be merged
        if len(doc.chunks) == 1: 
            # apply the merge function to the subchunks of the chunk
            single_chunk = doc.chunks[0]
            single_chunk.chunks = ChunkHandler.merge_too_short_chunks(single_chunk, min_chunk_size, recursive)
            return [single_chunk]

        new_chunks = []
        # If a chunks is too short, we add it to this list and merge with following chunks
        short_chunks_to_be_merged = []
        # iterate over chunks from first to last
        for i, chunk in enumerate(doc.chunks):
            # if the length of the chunk is NOT too short, we can merge it with the previous chunks and add it to the list of new chunks
            if chunk.len >= min_chunk_size:
                new_chunks.append(ChunkHandler.merge_multiple_chunks_into_one(short_chunks_to_be_merged + [chunk]))
                # clean the list with chunks to be merged
                short_chunks_to_be_merged = []
                continue
            # if the length of the chunk is too short
            else:
                # add the chunk to the list of chunks to be merged
                short_chunks_to_be_merged.append(chunk) 
                # check if the length of all chunks to be merged would exceed the minimum length
                len_of_all_chunks_to_merge = sum([short_chunk.len for short_chunk in short_chunks_to_be_merged])
                # when the length is now enough, merge all chunks in the list with the current chunk into a new one
                # of when we reached the last chunk
                if len_of_all_chunks_to_merge >= min_chunk_size or i == len(doc.chunks)-1:
                    merged_chunk = ChunkHandler.merge_multiple_chunks_into_one(short_chunks_to_be_merged)
                    new_chunks.append(merged_chunk)
                    # clean the list with chunks to be merged
                    short_chunks_to_be_merged = []
                    continue
                # otherwise continue to next chunk
                else: continue

        # if the last chunk is still too short, append it to chunk before (the pre-last chunk)
        if new_chunks[-1].len < min_chunk_size and len(new_chunks) >= 2:
            new_chunks = new_chunks[:-2] + [ChunkHandler.merge_two_chunks(new_chunks[-2], new_chunks[-1])]

        # when recursive merging is required, repeat the merges for each of the sub chunks
        # short sub-chunks will be merged and thus don't have sub-chunks, but longer chunks will still have sub-chunks
        if recursive:
            # sub_chunks = [sub_chunk for new_chunk in new_chunks for sub_chunk in new_chunk.chunks]
            for merged_chunk in new_chunks:
                merged_chunk.chunks = ChunkHandler.merge_too_short_chunks(merged_chunk, min_chunk_size, recursive=True)

        return new_chunks
    

    @staticmethod
    def print_doc_from_chunks(doc: MarkdownDocument, print_title_too=True):
        """Used for debugging chunking step. Print the text of all chunks and sub-chunks.
        The resulted text should have the same structure as the original document.
        Use recursive approach!"""
        # If a chunk no longer has children, print the text of the chunk
        if not doc.chunks:
            if print_title_too: print(doc.title)
            print(doc.text)
        else:
            if print_title_too: print(doc.title)
            # otherwise print the children chunks
            for chunk in doc.chunks:
                ChunkHandler.print_doc_from_chunks(chunk)

    
    @staticmethod
    def merge_two_chunks(first, other, maintain_sub_chunks:bool=True):
        """
        Creates a new chunk by combining two chunks together.
        @param maintain_sub_chunks: specifies if the sub-chunks of the merged chunks should be maintained.
                                    This is not necessary, when two short chunks have been merged together as they should not have any sub-chunks.
        """
        return ChunkHandler.merge_multiple_chunks_into_one([first, other], maintain_sub_chunks)
        # TODO: remove the code below... why? We started with a merge_two_chunks class and added a merge for a list of chunks later.
        if isinstance(other, Chunk) and first.parent.title == other.parent.title:
            combined_chunk = Chunk(
                first.text + '\n' + other.text, 
                first.parent, first.chunk_level, 
                min(first.chunk_pos, other.chunk_pos),
                min(first.page_number, other.page_number),
                is_merged_chunk = True)
            combined_chunk.context = first.context
            if maintain_sub_chunks:
                combined_chunk.chunks = first.chunks + other.chunks
            return combined_chunk
        else:
            raise TypeError(
                "Both operands must be 'Chunk' objects and have the same parent!"+\
                f"However, types were {type(first)} and {type(other)} and parents were {first.parent.title} and {other.parent.title}")
        

    @staticmethod
    def merge_multiple_chunks_into_one(chunks:list[Chunk], maintain_sub_chunks:bool=True):
        # if there is only one single chunk to be merged, just return the chunk itself
        if len(chunks) == 1: return chunks[0]

        # all items in list must be chunks
        assert all([isinstance(chunk, Chunk) for chunk in chunks]), "All items in the list must be chunks!"
        # all chunks should have the same parent, only a single unique parent
        unique_chunk_parent_titles = set([chunk.parent.title for chunk in chunks])
        assert len(unique_chunk_parent_titles) == 1, "All chunks to be merged must have the same parent but parents were: " + str(unique_chunk_parent_titles)

        # first chunk determines the metadata of the new combined chunk
        first_chunk = chunks[0]
        combined_chunk = Chunk(
            chunk_text = "\n\n".join([chunk.text for chunk in chunks]),
            parent = first_chunk.parent,
            level = first_chunk.chunk_level,
            chunk_pos = first_chunk.chunk_pos,
            page_number = first_chunk.page_number,
            is_merged_chunk=True,
            title = first_chunk.title
        ) 

        # add context
        combined_chunk.context = first_chunk.context
        if maintain_sub_chunks:
            combined_chunk.chunks = [sub_chunk for chunk in chunks for sub_chunk in chunk.chunks]

        return combined_chunk
    
if __name__ == '__main__':
    # test the splitting functions
    text_short_lines = 'Installing the Venting Nozzle\n\nThe work steps for operator 1 should be carried out from the work platform.\n\nPersonnel:\n2 people, operator\n\nMaterial:\n1 venting nozzle\n\nRequirements\n\n— No bag is installed.\n\n— The tower and the supply box are switched on.\n\n— Emergency stop is not activated.\n\nProcedure\n\nOperator 1:\n\n \n* Insert the venting nozzle into one of the four quick couplings (1). \n\n \n* Open the venting nozzle (1). To do this, turn the lever (2) into the vertical \n\nposition.\n\n \n* Connect the venting nozzle to a drain or place a vessel underneath.\n\n\n\n[PAGE 61]\n\n<image: DeviceRGB, width: 412, height: 389, bpc: 8>\n\n<IMAGE 0 REMOVED>\n\n<image: DeviceRGB, width: 431, height: 394, bpc: 8>\n\n<IMAGE 1 REMOVED>\n\n<image: DeviceRGB, width: 457, height: 397, bpc: 8>\n\n<IMAGE 2 REMOVED>\n\nFilling with Heat Transfer Fluid and Performing First Venting\n\nThe work steps for operator 1 should be carried out from the work platform.\n\nProcedure\n\nOperator 2:\n\n \n* Open the temperature control circuit vent valve. To do this, turn the lever \nof the vent valve into the horizontal position.\n\n* \n CAUTION Danger of injury due to pressure being too high! The pres-\nsurization of the heat transfer fluid must not exceed the maximum \nvalue (for max. value, see Chapter “14.8 Heat Transfer Fluid”, \npage 179). Check the pressurization using the pressure gauge.\n\n \n* Open the filling and discharging port (1) for the heat transfer fluid. To do \n\nthis, turn the handle of the filling and discharging port into the horizontal \nposition.\n\n \n* Open the heat transfer fluid supply at the installation site.\n\n \n* The double wall and the temperature control circuit are filled with the \nheat transfer fluid.\n\n \n* Once only heat transfer fluid is emerging from the vent valve: Close the \nvent valve. To do this, turn the lever of the vent valve into the vertical po-\nsition. \n \n* The double wall continues to fill with heat transfer fluid.\n\n \n* Once only heat transfer fluid is emerging from the venting nozzle: Close \nthe heat transfer fluid supply.\n\nOperator 1:\n\n \n* Close the venting nozzle. To do this, turn the lever (1) into the horizontal \n\nposition.\n\n \n* Insert the venting nozzle into the next quick coupling.\n\n \n* Connect the venting nozzle to a drain or place a vessel underneath.\n\n \n* Open the venting nozzle. To do this, turn the lever into the vertical posi-\ntion.\n\nOperator 2:\n\n \n* Open the heat transfer fluid supply.\n\n \n* The double wall continues to fill with heat transfer fluid.\n\n \n* Once only heat transfer fluid is emerging from the venting nozzle: Close \nthe heat transfer fluid supply.\n\n\n\n[PAGE 62]\n\n<image: DeviceRGB, width: 457, height: 397, bpc: 8>\n\n<IMAGE 0 REMOVED>\n\nOperator 1 and 2:\n\n \n* Repeat the process for the two remaining quick couplings.\n\n \n* When the temperature control circuit and double wall are filled: Check \nthe temperature control circuit for leaks.\n\n \n* If a leak is found: Do not operate the temperature control circuit.\n\n \n* Repair the leak.\n\n \n* Repeat the filling process.\n\nPerforming the Second Venting\n\nThe work steps for operator 1 should be carried out from the work platform.\n\nPersonnel:\n2 people, operator\n\nMaterial:\n1 venting nozzle\n\nRequirements\n\nThe temperature sensor is installed and connected (see temperature sensor \ninstructions).\n\nProcedure\n\nOperator 1:\n\n \n* Open the venting nozzle. To do this, turn the lever into the vertical \nposition.\n\nOperator 2:\n\n \n* Set the “TEMP” temperature controller to 10°C (see device software \ninstructions).\n \n* The pump pumps at the maximum flow rate and the cooling valve opens.\n\n \n* Wait 30 minutes.\n\n \n* Turn off the “TEMP” temperature controller.\n\n* \n CAUTION Danger of injury due to pressure being too high! The pres-\nsurization of the heat transfer fluid must not exceed the maximum \nvalue (for max. value, see Chapter “5.10 Setting up the Temperature \nControl Circuit for Biostat STR\n 2000 L”, page 57). Check the pres-\nsurization using the pressure gauge.\n\n\n\n[PAGE 63]\n\n \n* Open the filling and discharging port for the heat transfer fluid. To do \nthis, turn the handle of the filling and discharging port into the horizontal \nposition. \n \n* The double wall and the temperature control circuit are filled with the \nheat transfer fluid.\n\n \n* Once only heat transfer fluid is emerging from the venting nozzle: Close \nthe heat transfer fluid supply.\n\nOperator 1:\n\n \n* Close the venting nozzle. To do this, turn the lever (1) into the horizontal \n\nposition.\n\n \n* Insert the venting nozzle into the next quick coupling.\n\n \n* Connect the venting nozzle to a drain or place a vessel underneath.\n\n \n* Open the venting nozzle. To do this, turn the lever into the vertical posi-\ntion.\n\nOperator 2:\n\n \n* Open the heat transfer fluid supply.\n\n \n* Once only heat transfer fluid is emerging from the venting nozzle: Close \nthe heat transfer fluid supply.\n\nOperator 1 and 2:\n\n \n* Repeat the process for the three remaining quick couplings.\n\nPerforming the Third Venting\n\nThe work steps for operator 1 should be carried out from the work platform.\n\nPersonnel:\n2 people, operator\n\nMaterial:\n1 venting nozzle\n\n\n| | WARNING |\n| | Danger of burns due to hot components in temperature control circuit! |\n| | * Avoid contact with hot surfaces of the temperature control circuit. |\n\n\nProcedure\n\nOperator 1:\n\n \n* Close the venting nozzle.\n\n\n\n[PAGE 64]\n\nOperator 2:\n\n \n* Set the “TEMP” temperature controller to 30°C (see device software in-\nstructions).\n \n* The system heats up.\n\n \n* Wait 30 minutes.\n\n \n* Turn off the temperature controller.\n\nOperator 1:\n\n \n* Open the venting nozzle.\n\nOperator 2:\n\n* \n CAUTION Danger of injury due to pressure being too high! The pres-\nsurization of the heat transfer fluid must not exceed the maximum \nvalue (for max. value, see Chapter “14.11 Gas and Compressed Air Sup-\nply”, page 180). Check the pressurization using the pressure gauge.\n\n \n* Open the filling and discharging port for the heat transfer fluid. To do \nthis, turn the handle of the filling and discharging port into the horizontal \nposition.\n\n \n* Open the heat transfer fluid supply at the installation site.\n\n \n* The double wall and the temperature control circuit are filled with the \nheat transfer fluid.\n\n \n* Once only heat transfer fluid is emerging from the venting nozzle: Close \nthe heat transfer fluid supply at the installation site.\n\nOperator 1:\n\n \n* Close the venting nozzle. To do this, turn the lever into the horizontal po-\nsition.\n\n \n* Insert the venting nozzle into the next quick coupling.\n\n \n* Connect the venting nozzle to a drain or place a vessel underneath.\n\n \n* Open the venting nozzle. To do this, turn the lever into the vertical \nposition.\n\nOperator 2:\n\n \n* Open the heat transfer fluid supply.\n\n \n* Once only heat transfer fluid is emerging from the venting nozzle: Close \nthe heat transfer fluid supply.\n\nOperator 1 and 2:\n\n \n* Repeat the process for the three remaining quick couplings.\n\n\n\n[PAGE 65]\n\nEnding Venting\n\nThe work steps for operator 1 should be carried out from the work platform.\n\nPersonnel:\n2 people, operator\n\nMaterial:\n1 venting nozzle\n\n\n| Danger of burns due to hot components in temperature control circuit! | |\n| * Avoid contact with hot surfaces of the temperature control circuit. | |\n| Danger of scaling if hot heat transfer fluid escapes! | |\n| Hot heat transfer fluid may escape if the temperature control circuit leaks or | |\n| overheats. | |\n| * If heat transfer fluid is leaking: Decommission the device. | |\n\n\nProcedure\n\nOperator 2:\n\n \n* Set the heat transfer fluid to 10°C again and vent the temperature con-\ntrol circuit at 0.8 bar.\n\nOperator 1:\n\n \n* Close the venting nozzle. To do this, turn the lever into the horizontal po-\nsition.\n\n \n* Remove the venting nozzle.\n\n \n* The double wall and temperature control circuit are vented.\n\nOperator 1 and 2:\n\n \n* If you can still hear any noises from air bubbles in the double wall: Repeat \nthe venting procedure.\n\n \n* Turn off the temperature controller.\n\n \n* To prevent the valves opening after the filling procedure: Secure the \nvalves against opening with cable clips.\n\n\n\n[PAGE 66]\n\n<image: DeviceCMYK, width: 420, height: 357, bpc: 8>\n\n<IMAGE 0 REMOVED>'
    splits = ChunkHandler.split_by_short_lines_that_might_be_headers(text_short_lines)
    print(splits)